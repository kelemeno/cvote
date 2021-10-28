# To run this demo, type:
#   python3 -m demo.amm_demo.demo
# .

import argparse
import os
import random
import subprocess
from time import sleep
from typing import Dict

from web3 import HTTPProvider, Web3, eth

# import cairo code
# erdekes, hogy ezt csak igy meg lehet csinalni
#esztetikusabb, ha demo.amm_demo.prove_batch.py, de nem biztos hogy elfogadja, hagyjuk igy. 
from demo.vote_demo.prove_batch_cvote import Account, Balance, BatchProver, VoteTransaction #ezek classok
from starkware.cairo.bootloader.hash_program import compute_program_hash_chain
from starkware.cairo.common.small_merkle_tree import MerkleTree
from starkware.cairo.lang.vm.crypto import get_crypto_lib_context_manager, pedersen_hash
from starkware.cairo.sharp.sharp_client import init_client

N_ACCOUNTS = 5
N_BATCHES = 1
MIN_OPERATOR_BALANCE = 0.1 * 10 ** 18
BATCH_SIZE = 3
GAS_PRICE = 10000000000
AMM_SOURCE_PATH = os.path.join(os.path.dirname(__file__), "cvote.cairo")
CONTRACT_SOURCE_PATH = os.path.join(os.path.dirname(__file__), "cvote_contract.sol")


def init_prover(bin_dir: str, node_rpc_url: str) -> BatchProver:
    """
    Initializes the vote counter client, with zeros.

    node_rpc_url: a URL of an Ethereum node RPC.
    """
    balance = Balance(a=0, b=0)
    accounts = {
        i: Account(
            pub_key=i,
        )
        for i in range(N_ACCOUNTS)
    }
    sharp_client = init_client(bin_dir=bin_dir, node_rpc_url=node_rpc_url)
    program = sharp_client.compile_cairo(source_code_path=AMM_SOURCE_PATH)
    prover = BatchProver(
        program=program, balance=balance, accounts=accounts, sharp_client=sharp_client
    )

    return prover


def deploy_contract(batch_prover: BatchProver, w3: Web3, operator: eth.Account) -> eth.Contract:
    """
    Deploys the AMM demo smart-contract and returns its address.
    The contract is initialized with the current state of the batch_prover.

    batch_prover: a BatchProver instance.
    w3: a web3 Ethereum client.
    operator: the account deploying the contract.
    """

   # account_tree_root = get_merkle_root(batch_prover.accounts)
    amount_token_a = batch_prover.balance.a
    amount_token_b = batch_prover.balance.b
    program_hash = compute_program_hash_chain(batch_prover.program)
    cairo_verifier = batch_prover.sharp_client.contract_client.contract.address

    # Compile the smart contract.
    #breakpoint()
    print("Compiling the AMM demo smart contract...")
    artifacts = (
        subprocess.check_output(["solc", "--bin", "--abi", CONTRACT_SOURCE_PATH])
        .decode("utf-8")
        .split("\n")
    )
    bytecode = artifacts[3]
    abi = artifacts[5]
    new_contract = w3.eth.contract(abi=abi, bytecode=bytecode)
   ## print(account_tree_root, amount_token_a,amount_token_b,program_hash,cairo_verifier, abi, bytecode)
    ##2967557441972688032532974552833232470560369835622197258380374934912759346522 86936761 54178317 2523556208598399685092448573215262490339147880504183956623043299586720619041 0xAB43bA48c9edF4C2C4bB01237348D1D7B28ef168
##this runs with the other program

##1133241622275725814223971999546247521430565862767695490606429333213530292302 0 0 2763908502453229549527775066481247394153308217029680038552310002712944303626 0xAB43bA48c9edF4C2C4bB01237348D1D7B28ef168
##it does not run with this

        
    transaction = new_contract.constructor(
       #accountTreeRoot=account_tree_root,
        amountTokenA=amount_token_a,
        amountTokenB=amount_token_b,
        cairoProgramHash=program_hash,
        cairoVerifier=cairo_verifier,
    )
    
    print("Deploying the AMM demo smart contract...")
    tx_receipt = send_transaction(w3, transaction, operator)
    assert (
        tx_receipt["status"] == 1
    ), f'Failed to deploy contract. Transaction hash: {tx_receipt["transactionHash"]}.'

    contract_address = tx_receipt["contractAddress"]
    print(
        f"AMM demo smart contract successfully deployed to address {contract_address}. ",
        "You can track the contract state through this link ",
        f"https://goerli.etherscan.io/address/{contract_address} .",
        "Press enter to continue."
    )

    return w3.eth.contract(abi=abi, address=contract_address)


def main():
    """
    The main demonstration program.
    """

    parser = argparse.ArgumentParser(description="AMM demo")
    parser.add_argument(
        "--bin_dir",
        type=str,
        default="",
        help="The path to a directory that contains the cairo-compile and cairo-run scripts. "
        "If not specified, files are assumed to be in the system's PATH.",
    )

    args = parser.parse_args()

    # Connect to an Ethereum node.
    node_rpc_url = "https://goerli.infura.io/v3/b76793dac63d4bda8c2aae5bf8348440"
    w3 = Web3(HTTPProvider(node_rpc_url))
    if not w3.isConnected():
        print("Error: could not connect to the Ethereum node.")
        exit(1)

    # Initialize Ethereum account for on-chain transaction sending.
    operator_private_key_str = "43cb30f6aa228b91cd22a9f54e0fb1fd72d2d7777bc5bcfea1dcadb7481149fd"
    try:
        operator_private_key = int(operator_private_key_str, 16)
    except ValueError:
        print("Generating a random key...")
        operator_private_key = random.randint(0, 2 ** 256)
    operator_private_key = "0x{:064x}".format(operator_private_key)
    operator = eth.Account.from_key(operator_private_key)

    # Ask for funds to be transferred to the operator account id its balance is too low.
    if w3.eth.getBalance(operator.address) < MIN_OPERATOR_BALANCE:
        input(
            f"Please send funds (at least {MIN_OPERATOR_BALANCE * 10**-18} Goerli ETH) "
            f"to {operator.address} and press enter."
        )
        while w3.eth.getBalance(operator.address) < MIN_OPERATOR_BALANCE:
            print("Funds not received yet...")
            sleep(15)

    # Initialize the system.
    prover = init_prover(bin_dir=args.bin_dir, node_rpc_url=node_rpc_url)
    amm_contract = deploy_contract(prover, w3, operator)

    # Generate and prove batches.
    for _ in range(N_BATCHES):
        batch = [rand_transaction() for _ in range(BATCH_SIZE)]

        print("Sending batch to SHARP...")
        job_id, fact, program_output = prover.prove_batch(batch)

        print()
        print(f"Waiting for the fact {fact} to be registered on-chain...")
        mins = 0.0
        while not prover.sharp_client.fact_registered(fact):
            status = prover.sharp_client.get_job_status(job_id)
            print(
                f"Elapsed: {mins} minutes. Status of job id '{job_id}' "
                f"and fact '{fact}' is '{status}'."
            )
            sleep(15)
            mins += 0.25

        print()
        print("Updating on-chain state...")
        transaction = amm_contract.functions.updateState(programOutput=program_output)
        tx_receipt = send_transaction(w3, transaction, operator)
        assert tx_receipt["status"] == 1, (
            "Failed to update the on-chain state. "
            f'Transaction hash: {tx_receipt["transactionHash"]}.'
        )
        print()
    print("AMM Demo finished successfully :)")


def tx_kwargs(w3: Web3, sender_account: eth.Account):
    """
    Helper function used to send Ethereum transactions.

    w3: a web3 Ethereum client.
    sender_account: the account sending the transaction.
    """
    nonce = w3.eth.getTransactionCount(sender_account)
    return {"from": sender_account, "gas": 10 ** 6, "gasPrice": GAS_PRICE, "nonce": nonce}


def send_transaction(w3, transaction, sender_account: eth.Account):
    """
    Sends an Ethereum transaction and waits for it to be mined.

    w3: a web3 Ethereum client.
    transaction: the transaction to be sent.
    sender_account: the account sending the transaction.
    """
    transaction_dict = transaction.buildTransaction(tx_kwargs(w3, sender_account.address))
    signed_transaction = sender_account.signTransaction(transaction_dict)
    print("Transaction built and signed.")
    tx_hash = w3.eth.sendRawTransaction(signed_transaction.rawTransaction).hex()
    print(f"Transaction sent. tx_hash={tx_hash} .")
    receipt = w3.eth.waitForTransactionReceipt(tx_hash)
    print("Transaction successfully mined.")
    return receipt



def get_merkle_root(accounts: Dict[int, Balance]) -> int:
    """
    Returns the merkle root given accounts state.

    accounts: the state of the accounts (the merkle tree leaves).
    """
    tree = MerkleTree(tree_height=10, default_leaf=0)
    return tree.compute_merkle_root(
        [
            (i, pedersen_hash(a.pub_key, a.pub_key))
            for i, a in accounts.items()
        ]
    )


def rand_transaction() -> VoteTransaction:
    """
    Draws a random Vote transaction.
    """
    return VoteTransaction(
        account_id=random.randint(0, N_ACCOUNTS - 1), token_a_amount=random.randint(1, 1000), token_b_amount=random.randint(1, 1000)
    )


if __name__ == "__main__":
    with get_crypto_lib_context_manager("Release"):
        main()

