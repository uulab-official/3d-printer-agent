import unittest
from print_agent.offers import compare_offers


class OffersTests(unittest.TestCase):
    def test_unrealistic_tiny_weight_cannot_crash_decimal_quantization(self):
        with self.assertRaises(ValueError):
            compare_offers([{'name':'invalid','price':10000,'grams':'1e-1000','shipping':0}])
    def test_delivered_price_normalization(self):
        result = compare_offers([
            {'name':'A','price':12000,'grams':1000,'shipping':3000,'currency':'KRW'},
            {'name':'B','price':7000,'grams':500,'shipping':0,'currency':'KRW'},
        ])
        self.assertEqual(result['groups']['KRW'][0]['name'], 'B')
        self.assertEqual(result['groups']['KRW'][0]['price_per_kg'], 14000)
        self.assertEqual(result['source'], 'user_entered')

    def test_unknown_shipping_never_means_free(self):
        result=compare_offers([{'name':'A','price':12000,'grams':1000,'shipping':None,'currency':'KRW'}])
        self.assertIsNone(result['groups']['KRW'][0]['delivered_total'])
        self.assertIsNone(result['groups']['KRW'][0]['price_per_kg'])
        self.assertFalse(result['live_prices'])

    def test_different_currencies_are_not_ranked_together(self):
        result=compare_offers([
            {'name':'A','price':12000,'grams':1000,'shipping':0,'currency':'KRW'},
            {'name':'B','price':10,'grams':1000,'shipping':0,'currency':'USD'},
        ])
        self.assertEqual(set(result['groups']), {'KRW','USD'})

    def test_zero_weight_and_nonfinite_prices_rejected(self):
        for key,value in [('grams',0),('price',-1),('price',float('nan')),('shipping',-3)]:
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                offer={'name':'A','price':1,'grams':1000,'shipping':0,'currency':'KRW'}
                offer[key]=value
                compare_offers([offer])


if __name__ == '__main__':
    unittest.main()
