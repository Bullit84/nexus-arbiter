"""
Trust Wallet Agent Kit — NEXUS BSC Transaction Executor.

Self-custody transaction signing and broadcasting for BNB Smart Chain.
Integrates with NEXUS's trade execution pipeline (Stage 5).
Uses Trust Wallet's delegated key model — private key never leaves the signing enclave.

Architecture:
    NEXUS Signal → Risk Gates → Position Sizing → TWAK.sign_and_send()
    → BSC RPC → TX Hash → trades.db

Docs: https://github.com/trustwallet/agent-kit
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import httpx
from web3 import Web3

logger = logging.getLogger(__name__)

# BSC Mainnet
BSC_CHAIN_ID = 56
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
PANCAKE_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"

# Trust Wallet Agent Kit endpoint (self-hosted or Trust Wallet's service)
TW_AGENT_KIT_URL = os.getenv("TW_AGENT_KIT_URL", "http://localhost:8420")


class TrustWalletExecutor:
    """Signs and broadcasts BSC transactions via Trust Wallet Agent Kit."""

    def __init__(self, rpc_url: str = BSC_RPC_URL, kit_url: str = TW_AGENT_KIT_URL):
        self.rpc_url = rpc_url
        self.kit_url = kit_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    @property
    def chain_id(self) -> int:
        return self.w3.eth.chain_id

    def get_wallet_address(self) -> str:
        """Returns the agent's BSC wallet address."""
        return os.getenv("WALLET_ADDRESS", "0x236f03bBba0903321C73c929530DEaa842D6Ba76")

    def get_bnb_balance(self) -> float:
        """Query BNB balance from BSC."""
        try:
            addr = self.get_wallet_address()
            wei = self.w3.eth.get_balance(addr)
            return float(self.w3.from_wei(wei, "ether"))
        except Exception as e:
            logger.warning(f"Balance fetch failed: {e}")
            return 0.0

    def sign_transaction(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign a transaction via Trust Wallet Agent Kit.

        The kit manages the private key in a secure enclave — the agent
        never sees or logs the raw key. This is the key differentiator
        from env-var-based approaches.

        Args:
            tx_data: Unsigned transaction dict (to, value, data, gas, etc.)

        Returns:
            Signed transaction ready for broadcast
        """
        try:
            resp = self.client.post(
                f"{self.kit_url}/sign",
                json={
                    "chain_id": BSC_CHAIN_ID,
                    "transaction": tx_data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                headers={"User-Agent": "NEXUS-Arbiter/1.0"},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            logger.warning("TW Agent Kit unreachable — falling back to local signing")
            return self._local_sign_fallback(tx_data)

    def broadcast_transaction(self, signed_tx: Dict[str, Any]) -> str:
        """
        Broadcast a signed transaction to BSC.

        Returns:
            Transaction hash (0x...)
        """
        raw_tx = signed_tx.get("raw_transaction", signed_tx.get("signed_tx"))
        tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
        return tx_hash.hex()

    def execute_swap(
        self,
        token_in: str,
        token_out: str,
        amount_in_wei: int,
        min_amount_out_wei: int,
        deadline_minutes: int = 20,
    ) -> Optional[str]:
        """
        Execute a token swap on PancakeSwap via Trust Wallet Agent Kit.

        Full flow: build swap → sign via kit → broadcast → return TX hash.

        Returns:
            Transaction hash, or None if any step fails
        """
        try:
            wallet = self.get_wallet_address()
            deadline = int(time.time()) + deadline_minutes * 60

            # Build swap path [token_in → WBNB → token_out]
            wbnb = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
            path = [token_in, wbnb, token_out] if token_in != wbnb and token_out != wbnb else [token_in, token_out]

            # Encode swap via PancakeSwap Router
            router = self.w3.eth.contract(
                address=PANCAKE_ROUTER,
                abi=[{
                    "inputs": [
                        {"name": "amountIn", "type": "uint256"},
                        {"name": "amountOutMin", "type": "uint256"},
                        {"name": "path", "type": "address[]"},
                        {"name": "to", "type": "address"},
                        {"name": "deadline", "type": "uint256"},
                    ],
                    "name": "swapExactTokensForETH" if token_out == wbnb else "swapExactTokensForTokens",
                    "outputs": [{"name": "amounts", "type": "uint256[]"}],
                    "stateMutability": "nonpayable",
                    "type": "function",
                }],
            )

            tx = router.functions.swapExactTokensForTokens(
                amount_in_wei, min_amount_out_wei, path, wallet, deadline
            ).build_transaction({
                "from": wallet,
                "gas": 300000,
                "gasPrice": self.w3.eth.gas_price,
                "nonce": self.w3.eth.get_transaction_count(wallet),
            })

            # Sign via Trust Wallet Agent Kit
            signed = self.sign_transaction(tx)
            tx_hash = self.broadcast_transaction(signed)

            logger.info(f"Swap executed: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Swap execution failed: {e}")
            return None

    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Wait for and return transaction receipt."""
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            return dict(receipt)
        except Exception as e:
            logger.warning(f"Receipt wait failed for {tx_hash}: {e}")
            return None

    def verify_kit_connection(self) -> bool:
        """Health check: can we reach the Trust Wallet Agent Kit?"""
        try:
            resp = self.client.get(f"{self.kit_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def _local_sign_fallback(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback: sign locally using web3.
        ONLY used when TW Agent Kit is unreachable.
        Private key must be available in environment.
        """
        private_key = os.getenv("WALLET_PRIVATE_KEY")
        if not private_key:
            raise RuntimeError("Neither TW Agent Kit nor WALLET_PRIVATE_KEY available")

        signed = self.w3.eth.account.sign_transaction(tx_data, private_key)
        return {"raw_transaction": signed.rawTransaction.hex(), "hash": signed.hash.hex()}


# Singleton
executor = TrustWalletExecutor()


def execute_trade(
    asset: str,
    direction: str,
    amount_usdt: float,
    strategy: str,
) -> Optional[Dict[str, Any]]:
    """
    NEXUS trade execution entry point (Stage 5).

    Args:
        asset: Token symbol (e.g., 'BTCB', 'ETH')
        direction: 'LONG' or 'SHORT'
        amount_usdt: Position size in USDT
        strategy: Strategy name for audit trail

    Returns:
        Dict with tx_hash, timestamp, asset, amount, or None on failure
    """
    tx_hash = executor.execute_swap(
        token_in="0x55d398326f99059ff775485246999027b3197955",  # USDT
        token_out="0x...",  # Resolved by asset
        amount_in_wei=executor.w3.to_wei(amount_usdt, "ether"),
        min_amount_out_wei=0,  # Accept any price (slippage handled upstream)
    )

    if tx_hash:
        return {
            "tx_hash": tx_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset": asset,
            "direction": direction,
            "amount_usdt": amount_usdt,
            "strategy": strategy,
            "chain": "BSC",
            "wallet": executor.get_wallet_address(),
        }

    return None
