pragma solidity ^0.5.2;

contract IFactRegistry {
    /*
      Returns true if the given fact was previously registered in the contract.
    */
    function isValid(bytes32 fact) external view returns (bool);
}

/*
  AMM demo contract.
  Maintains the AMM system state hash.
*/
contract CvoteDemo {
    

    
    // On-chain tokens balances.
    uint256 amountTokenA_;
    uint256 amountTokenB_;

    // The Cairo program hash.
    uint256 cairoProgramHash_;

    // The Cairo verifier.
    IFactRegistry cairoVerifier_;

    //Declare an Event
    event Change(uint256 avalue, uint256 bvalue);
    /*
      Initializes the contract state.
    */
    constructor(
        
        uint256 amountTokenA,
        uint256 amountTokenB,
        uint256 cairoProgramHash,
        address cairoVerifier
    ) public {
       
        amountTokenA_ = amountTokenA;
        amountTokenB_ = amountTokenB;
        cairoProgramHash_ = cairoProgramHash;
        cairoVerifier_ = IFactRegistry(cairoVerifier);
        //Emit an event
        emit Change(amountTokenA_, amountTokenB_);
    }
    
   

    function updateState(uint256[] memory programOutput) public {
        // Ensure that a corresponding proof was verified.
        bytes32 outputHash = keccak256(abi.encodePacked(programOutput));
        bytes32 fact = keccak256(abi.encodePacked(cairoProgramHash_, outputHash));
        require(cairoVerifier_.isValid(fact), "MISSING_CAIRO_PROOF");

        // Ensure the output consistency with current system state.
        require(programOutput.length == 4, "INVALID_PROGRAM_OUTPUT");
       // require(accountTreeRoot_ == programOutput[4], "ACCOUNT_TREE_ROOT_MISMATCH");
        require(amountTokenA_ == programOutput[0], "TOKEN_A_MISMATCH");
        require(amountTokenB_ == programOutput[1], "TOKEN_B_MISMATCH");

        // Update system state.
        
        amountTokenA_ = programOutput[2];
        amountTokenB_ = programOutput[3];
        
        //Emit an event
        emit Change(amountTokenA_, amountTokenB_);
    }
}
