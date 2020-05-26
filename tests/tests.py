import unittest
from app import User
from data import vk_api
from unittest.mock import patch


class TestMainApiFunctions(unittest.TestCase):
    def setUp(self):
        self.user = User("ilya_dmitrenko")
        self.api_key = vk_api
        #self.user.authorization = '74467c5456ee9df843ce8f48ddb38c437fb301efd7e381fafde1081347130341b04c3a862d94464984dc2'


    def test_auth(self):
        with patch('app.input',
                   return_value=''): # подставить токен, который генерируется после перехода по ссылке
            result = self.user.authorization()
            print(result)
        self.assertEqual(len(result), 85)

    def test_users_bdate(self):
        with patch('app.input', return_value='RHCP'):
            result = self.user.getUserInfo()

        self.assertGreater(len(result["bdate"]), 8)

    def test_find_duplicates_in_database(self):
        db_connect = self.user.connect_to_db()
        check_user_existance_lst = list()
        check_user_existance = list(db_connect.find({}, {"id": 1}))
        for element in check_user_existance:
            check_user_existance_lst.append(element["id"])
        self.assertEqual(len(check_user_existance_lst), len(set(check_user_existance_lst)))

    def test_write_in_database(self):
        with patch('app.input', side_effect='a'):

            db_connect = self.user.connect_to_db()
            check_user_existance = list(db_connect.find())
            self.user.write_to_db('most_common_people.json')
            db_connect_2 = self.user.connect_to_db()
            check_user_existance_again = list(db_connect_2.find())
        self.assertGreater(len(check_user_existance_again), len(check_user_existance))


if __name__ == '__main__':
    unittest.main()
