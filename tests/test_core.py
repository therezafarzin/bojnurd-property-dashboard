import unittest
from money import parse_money, extract_sell_prices
from neighborhoods import canonical_district
from dedupe import is_strong_duplicate
from collector import DivarCollector

class CoreTests(unittest.TestCase):
    def test_money_full(self):
        self.assertEqual(parse_money('۵٬۴۰۰٬۰۰۰٬۰۰۰ تومان'), 5_400_000_000)
    def test_money_billions(self):
        self.assertEqual(parse_money('۳.۵ میلیارد تومان'), 3_500_000_000)
    def test_extract(self):
        total, ppm = extract_sell_prices('۵ میلیارد تومان', 'متری ۴۰ میلیون تومان')
        self.assertEqual(total, 5_000_000_000)
        self.assertEqual(ppm, 40_000_000)
    def test_district(self):
        self.assertEqual(canonical_district('فردوسی جنوبی'), 'فردوسی')

    def test_detail_parser(self):
        payload={"sections":[
            {"section_name":"LIST_DATA","widgets":[
                {"widget_type":"GROUP_INFO_ROW","data":{"items":[{"title":"متراژ","value":"۱۲۰"},{"title":"ساخت","value":"۱۴۰۴"},{"title":"اتاق","value":"۳"}]}},
                {"widget_type":"GROUP_FEATURE_ROW","data":{"items":[{"title":"آسانسور","available":True},{"title":"پارکینگ","available":True},{"title":"انباری ندارد","available":False}]}}
            ]},
            {"section_name":"DESCRIPTION","widgets":[{"widget_type":"DESCRIPTION_ROW","data":{"text":"نمونه توضیحات"}}]}
        ]}
        d=DivarCollector._parse_detail_payload(payload)
        self.assertEqual(d["size_m2"],120.0)
        self.assertEqual(d["year_built"],1404)
        self.assertEqual(d["rooms"],3)
        self.assertTrue(d["has_elevator"])
        self.assertFalse(d["has_storage"])

    def test_duplicate_conservative(self):
        a={'token':'a','district':'فردوسی','size_m2':100,'total_price':4_000_000_000,'year_built':1403,'rooms':2,'title':'آپارتمان ۱۰۰ متری فول امکانات','description':'واحد عالی فول امکانات طبقه دوم','image_url':'https://x/a.jpg'}
        b={**a,'token':'b'}
        self.assertTrue(is_strong_duplicate(b,a))

if __name__ == '__main__': unittest.main()
