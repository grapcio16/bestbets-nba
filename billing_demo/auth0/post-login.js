// Attach to the isolated Development tenant's Login flow. No Premium claims.
// Replace the API Identifier below if you choose a different one in Auth0.
exports.onExecutePostLogin = async (event, api) => {
  if (event.resource_server?.identifier !== 'https://bestbets-sandbox-api.example') return;
  if (event.user.email_verified !== true) {
    api.access.deny('Verify your email address, then log in again.');
    return;
  }
  api.accessToken.setCustomClaim(
    'https://bestbets-nba.streamlit.app/claims/email_verified', true
  );
};
