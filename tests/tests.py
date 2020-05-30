import unittest
from app import User
from unittest.mock import patch


class TestMainApiFunctions(unittest.TestCase):
    def setUp(self):
        self.user = User("id72625041")


    def test_auth(self):
        with patch('app.input',
                   return_value='d5d6f9950576942f1a5fc9bc5bcfe068b7507eabb84b32541f43f73672d2e5ca647e75a9a6ba7fede7ccb'):
            result = self.user.authorization()
        self.assertEqual(len(result), 85)

    def test_users_bdate(self):
        with patch('app.input',
                   return_value='d5d6f9950576942f1a5fc9bc5bcfe068b7507eabb84b32541f43f73672d2e5ca647e75a9a6ba7fede7ccb'):
            self.user.authorization()
        with patch('app.input', side_effect=['RHCP', 'movies']):
            result = self.user.getUserInfo()
        self.assertGreater(len(result["bdate"]), 8)

    def test_user_groups_count(self):
        with patch('app.input',
                   return_value='d5d6f9950576942f1a5fc9bc5bcfe068b7507eabb84b32541f43f73672d2e5ca647e75a9a6ba7fede7ccb'):
            self.user.authorization()
        result = self.user.get_groups()
        self.assertEqual(len(result), 51)

    def test_find_duplicates_in_database(self):
        db_connect = self.user.connect_to_db()
        check_user_existance_lst = list()
        check_user_existance = list(db_connect.find({}, {"id": 1}))
        for element in check_user_existance:
            check_user_existance_lst.append(element["id"])
        self.assertEqual(len(check_user_existance_lst), len(set(check_user_existance_lst)))

    def test_write_in_database(self):
        with patch('app.input',
                   return_value='d5d6f9950576942f1a5fc9bc5bcfe068b7507eabb84b32541f43f73672d2e5ca647e75a9a6ba7fede7ccb'):
            self.user.authorization()
        with patch('app.input', side_effect=['RHCP', 'movies', '1993']):
            db_connect = self.user.connect_to_db()
            check_user_existance = list(db_connect.find())
            self.user.write_to_db('most_common_people.json')
            db_connect_2 = self.user.connect_to_db()
            check_user_existance_again = list(db_connect_2.find())
        self.assertGreater(len(check_user_existance_again), len(check_user_existance))


if __name__ == '__main__':
    unittest.main()
