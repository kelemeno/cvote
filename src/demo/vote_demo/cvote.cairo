%builtins output pedersen range_check

from starkware.cairo.common.cairo_builtins import HashBuiltin
from starkware.cairo.common.dict import dict_new, dict_read, dict_squash, dict_update, dict_write
from starkware.cairo.common.dict_access import DictAccess
from starkware.cairo.common.hash import hash2
from starkware.cairo.common.math import assert_nn_le, unsigned_div_rem
from starkware.cairo.common.registers import get_fp_and_pc
from starkware.cairo.common.small_merkle_tree import small_merkle_tree

struct Account:
    member public_key : felt
end

# The maximum amount of each token that belongs to the AMM.
const MAX_BALANCE = 2 ** 64 - 1

struct AmmState:
    
    # The amount of the tokens currently in the AMM.
    # Must be in the range [0, MAX_BALANCE].
    member token_a_balance : felt
    member token_b_balance : felt
end

# Represents a vote transaction between a user and the AMM.
struct VoteTransaction:
    member account_id : felt
    member token_a_amount : felt
    member token_b_amount : felt
end

func vote{range_check_ptr}(state : AmmState, transaction : VoteTransaction*) -> (state : AmmState):
    alloc_locals

    tempvar a = transaction.token_a_amount
    tempvar b = transaction.token_b_amount
    
    a =a+ AmmState.token_a_balance
    b =b+ AmmState.token_b_balance

    # Update the state.
    local new_state : AmmState
    assert new_state.token_a_balance = a 
    assert new_state.token_b_balance = b 

    %{
        # Print the transaction values using a hint, for
        # debugging purposes.
        print(
            f'vote: Account {ids.transaction.account_id} '
            f'gave {ids.a} tokens of type token_a and '
            f'gave {ids.b} tokens of type token_b.')
    %}

    return (state=new_state)
end

func transaction_loop{range_check_ptr}(
        state : AmmState, transactions : VoteTransaction**, n_transactions) -> (state : AmmState):
    if n_transactions == 0:
        return (state=state)
    end

    let first_transaction : VoteTransaction* = [transactions]
    let (state) = vote(state=state, transaction=first_transaction)

    return transaction_loop(
        state=state, transactions=transactions + 1, n_transactions=n_transactions - 1)
end

func get_transactions() -> (transactions : VoteTransaction**, n_transactions : felt):
    alloc_locals
    local transactions : VoteTransaction**
    local n_transactions : felt
    %{
        transactions = [
            [
                transaction['account_id'],
                transaction['token_a_amount'],
                transaction['token_b_amount']
            ]
            for transaction in program_input['transactions']
        ]
        ids.transactions = segments.gen_arg(transactions)
        ids.n_transactions = len(transactions)
    %}
    return (transactions=transactions, n_transactions=n_transactions)
end

# The output of the AMM program.
struct AmmBatchOutput:
    # The balances of the AMM before applying the batch.
    member token_a_before : felt
    member token_b_before : felt
    # The balances of the AMM after applying the batch.
    member token_a_after : felt
    member token_b_after : felt
end

func main{output_ptr : felt*, pedersen_ptr : HashBuiltin*, range_check_ptr}():
    alloc_locals

    # Create the initial state.
    local state : AmmState
    %{
        # Initialize the balances using a hint.
        # Later we will output them to the output struct,
        # which will allow the verifier to check that they
        # are indeed valid.
        ids.state.token_a_balance = \
            0
        ids.state.token_b_balance = \
            0
    %}

    # Output the AMM's balances before applying the batch.
    let output = cast(output_ptr, AmmBatchOutput*)
    let output_ptr = output_ptr + AmmBatchOutput.SIZE

    assert output.token_a_before = state.token_a_balance
    assert output.token_b_before = state.token_b_balance

    # Execute the transactions.
    let (transactions, n_transactions) = get_transactions()
    let (state : AmmState) = transaction_loop(
        state=state, transactions=transactions, n_transactions=n_transactions)

    # Output the AMM's balances after applying the batch.
    assert output.token_a_after = state.token_a_balance
    assert output.token_b_after = state.token_b_balance

    return ()
end
