// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title InsightRegistry
/// @notice Lets a wallet owner anchor AI-generated reports about their wallet on-chain.
///         The report body lives off-chain (the API returns it, you could pin it to IPFS);
///         only its keccak256 hash and an optional URI are stored here, so anyone can later
///         verify that a given report is the one that was saved, without the chain
///         having to hold the full text.
contract InsightRegistry {
    struct Insight {
        bytes32 reportHash; // keccak256 of the report JSON
        string uri;         // optional pointer (ipfs://..., https://...), may be empty
        uint64 savedAt;     // block timestamp
        uint8 riskScore;    // 0-100 as computed by the AI service
    }

    /// wallet => list of insights saved by that wallet
    mapping(address => Insight[]) private _insights;

    event InsightSaved(
        address indexed wallet,
        uint256 indexed index,
        bytes32 reportHash,
        uint8 riskScore,
        string uri
    );

    error InvalidRiskScore(uint8 riskScore);
    error EmptyHash();

    /// @notice Save a report hash for msg.sender. Anyone can call; each wallet only writes its own list.
    function saveInsight(bytes32 reportHash, uint8 riskScore, string calldata uri)
        external
        returns (uint256 index)
    {
        if (reportHash == bytes32(0)) revert EmptyHash();
        if (riskScore > 100) revert InvalidRiskScore(riskScore);

        Insight[] storage list = _insights[msg.sender];
        index = list.length;
        list.push(Insight({
            reportHash: reportHash,
            uri: uri,
            savedAt: uint64(block.timestamp),
            riskScore: riskScore
        }));

        emit InsightSaved(msg.sender, index, reportHash, riskScore, uri);
    }

    function insightCount(address wallet) external view returns (uint256) {
        return _insights[wallet].length;
    }

    function getInsight(address wallet, uint256 index) external view returns (Insight memory) {
        return _insights[wallet][index];
    }

    /// @notice Return the most recent `limit` insights for a wallet, newest first.
    function latestInsights(address wallet, uint256 limit) external view returns (Insight[] memory out) {
        Insight[] storage list = _insights[wallet];
        uint256 n = list.length < limit ? list.length : limit;
        out = new Insight[](n);
        for (uint256 i = 0; i < n; i++) {
            out[i] = list[list.length - 1 - i];
        }
    }
}
