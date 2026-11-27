import unittest
from billing_sandbox_config import load_config,PREFIX

def fixture():
    return {PREFIX+k:v for k,v in {
      "STRIPE_KEY":"rk_test_abcdef0123456789",
      "STRIPE_ACCOUNT":"acct_fixture",
      "DATABASE_URL":"postgresql://hz_billing_sandbox_app:fixture@example.invalid/hoopzaro_billing_sandbox",
      "PRICE_ID":"price_fixture",
      "PRODUCT_ID":"prod_fixture",
      "RETURN_URL":"https://hoopzaro-billing-sandbox.streamlit.app/",
    }.items()}

class ConfigTests(unittest.TestCase):
    def test_valid(self):
        values,errors=load_config(fixture())
        self.assertFalse(errors)
        self.assertEqual(len(values),6)
    def test_invalid_account_url_not_exposed(self):
        env=fixture()
        raw="https://dashboard.stripe.com/acct_fixture/test/products"
        env[PREFIX+"STRIPE_ACCOUNT"]=raw
        values,errors=load_config(env)
        self.assertEqual(set(errors),{PREFIX+"STRIPE_ACCOUNT"})
        self.assertNotIn(raw,str(errors))
        self.assertNotIn("STRIPE_ACCOUNT",values)
    def test_missing_and_bad_values(self):
        env=fixture()
        env.pop(PREFIX+"PRICE_ID")
        env[PREFIX+"STRIPE_KEY"]="sk_live_private_fixture"
        env[PREFIX+"DATABASE_URL"]="postgresql://neondb_owner:private_fixture@example.invalid/hoopzaro_analytics"
        env[PREFIX+"RETURN_URL"]="https://hoopzaro.streamlit.app/"
        values,errors=load_config(env)
        self.assertEqual(set(errors),{PREFIX+x for x in ("PRICE_ID","STRIPE_KEY","DATABASE_URL","RETURN_URL")})
        self.assertNotIn("private_fixture",str(errors))
    def test_outer_whitespace(self):
        env=fixture()
        env[PREFIX+"STRIPE_ACCOUNT"]=" acct_fixture "
        values,errors=load_config(env)
        self.assertFalse(errors)
        self.assertEqual(values["STRIPE_ACCOUNT"],"acct_fixture")
if __name__=="__main__": unittest.main()
