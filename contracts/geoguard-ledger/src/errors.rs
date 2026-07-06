use soroban_sdk::contracterror;

/// Contract-specific error codes.
/// Returned as u32 error codes by the Soroban host.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
#[contracterror]
pub enum Error {
    NotInitialized = 1,
    AlreadyInitialized = 2,
    HashAlreadyAnchored = 3,
    HashNotFound = 4,
    Unauthorized = 5,
}
