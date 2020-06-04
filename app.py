import os
from pprint import pprint
import requests
import time
import json
from datetime import datetime
import re
from pymongo import MongoClient


class User:
    def __init__(self, id, access_token=''):
        self.id = id
        self.delta = 4
        self.V = '5.103'
        self.API = "https://api.vk.com/method"
        self.app_id = 7451978
        self.access_token = access_token
        self.connect_to_db = Database.connect_to_db(self)
    def authorization(self):
        url = f'https://oauth.vk.com/authorize?client_id={self.app_id}&display=popup&redirect_uri=https://oauth.vk.com' \
              f'/blank.html&scope=friends&response_type=token&v=5.103 '
        print(f'Чтобы получить токен для авторизации, перейдите по ссылке: {url}')
        self.access_token = input("Введите токен: ")
        return self.access_token

    def get_groups(self):
        group_set = set()
        params = {'access_token': self.access_token, 'user_id': self.resolveScreenName(self.id), 'v': self.V,
                  'extended': 0}
        try:
            response = requests.get(f'{self.API}/groups.get', params=params).json()['response']
            items = response.get('items')
            group_set = set(items)
        except KeyError:
            pass
        return group_set

    def resolveScreenName(self, screen_name):
        params = {'access_token': self.access_token, 'screen_name': screen_name, 'v': self.V}
        ID = requests.get(f"{self.API}/utils.resolveScreenName", params=params).json()['response']['object_id']
        return ID

    def getUserInfo(self):
        params = {'access_token': self.access_token, 'user_ids': self.resolveScreenName(self.id), 'fields':
            'city ,sex, bdate, music, movies', 'v': self.V}
        response = requests.get(f"{self.API}/users.get", params=params).json()['response'][0]
        for data in response:
            if response[data] == '':
                new_data = input(f"Заполните поле {data}: ")
                response[data] = new_data
        if 'city' not in response:
            city = input("Введите город: ")
            params = {'access_token': self.access_token, 'country_id': 1, 'q': city, 'v': self.V}
            city_request = requests.get(f"{self.API}/database.getCities", params=params).json()['response']['items'][0]
            response['city'] = city_request
        if 'bdate' not in response:
            bdate = input('Введите дату рождения в формате дд.мм.гггг: ')
            response['bdate'] = bdate
        if len(response['bdate']) < 8:
            response['bdate'] += '.' + input('Введите год рождения:')
        if 'music' not in response:
            response['music'] = input("Введите любимую музыку: ")
        return response

    def search_users_by_filter(self):
        target = self.getUserInfo()
        db_list = list()
        if target['sex'] == 2:
            filter_sex = 1
        elif target['sex'] == 1:
            filter_sex = 2
        filter_city = target['city']['id']
        today = datetime.strptime(datetime.today().strftime("%d.%m.%Y"), "%d.%m.%Y")
        bday = datetime.strptime(target['bdate'], "%d.%m.%Y")
        age = today.year - bday.year
        db_collection = self.connect_to_db
        db_users = list(db_collection.find({}, {'id': 1}))
        for index in db_users:
            db_list.append(index['id'])
        params = {'access_token': self.access_token, 'count': 1000, 'offset': len(db_users), 'city': filter_city,
                  'sex': filter_sex, 'status': 6, 'age_from': age - self.delta,
                  'age_to': age + self.delta, 'has_photo': 1, 'fields': 'music', 'v': self.V}
        searched_users = requests.get(f"{self.API}/users.search", params=params).json()['response']['items']
        for index in range(len(searched_users) - 1, -1, -1):
            searched_users[index]['weight'] = 0
            if searched_users[index]['id'] in db_list:
                searched_users.remove(searched_users[index])
        return target, searched_users

    def music_filter(self):
        source = self.search_users_by_filter()
        target = source[0]
        searched_users = source[1]
        music_filter = target['music']
        common_music = list()
        if ',' in music_filter:
            music_filter = music_filter.split(',')
        for user in searched_users:
            if type(music_filter) == list:
                try:
                    for element in music_filter:
                        a = re.search(re.compile(element, re.IGNORECASE), user['music'])
                        if a is not None:
                            common_music.append(a)
                    if len(common_music) > 0:
                        user['weight'] += 3
                        common_music = []
                except KeyError:
                    continue
            else:
                try:
                    a = re.search(re.compile(music_filter, re.IGNORECASE), user['music'])
                    if a is not None:
                        user['weight'] += 3
                except KeyError:
                    continue
        return target, searched_users

    def movies_filter(self):
        source = self.music_filter()
        target = source[0]
        searched_users = source[1]
        movies_filter = target['movies']
        common_movies = list()
        if ',' in movies_filter:
            movies_filter = movies_filter.split(',')
        for user in searched_users:
            if type(movies_filter) == list:
                try:
                    for element in movies_filter:
                        a = re.search(re.compile(element, re.IGNORECASE), user['movies'])
                        if a is not None:
                            common_movies.append(a)
                    if len(common_movies) > 0:
                        user['weight'] += 2
                        common_movies = []
                except KeyError:
                    continue
            else:
                try:
                    a = re.search(re.compile(movies_filter, re.IGNORECASE), user['movies'])
                    if a is not None:
                        user['weight'] += 2
                except KeyError:
                    continue
        return searched_users

    def mutual_friends_filter(self):
        target_uids_lst = []
        searched_users = self.movies_filter()
        offset = 0
        people_with_mutual = list()
        for user in searched_users:
            user_id = str(user["id"])
            user['link'] = f'https://vk.com/id{user_id}'
            target_uids_lst.append(user_id)
        for index in range(100, len(target_uids_lst), 100):
            user_ids = ','.join(target_uids_lst[offset: index - 1])
            offset += 100
            response = requests.get(
                f"{self.API}/friends.getMutual",
                params={"access_token": self.access_token, "v": self.V, "source_uid": self.resolveScreenName(self.id),
                        "target_uids": user_ids})
            time.sleep(0.3)
            print('***************')
            mutual_friends_info = response.json()["response"]
            for item in mutual_friends_info:
                if item['common_count'] > 0:
                    people_with_mutual.append(item['id'])
        for user in searched_users:
            if user['id'] in people_with_mutual:
                user['weight'] += 5
        return searched_users

    def get_groups_by_execute(self):
        search_list = self.mutual_friends_filter()
        list_to_execute = []
        target_groups = self.get_groups()
        offset = 25
        counter = 1
        in_progress = 0
        people_with_mutual_groups = list()
        users_groups = dict()
        for user in search_list:
            user_id = str(user["id"])
            list_to_execute.append(user_id)
        for index in range(0, len(list_to_execute), offset):
            list_to_execute = list_to_execute[offset * (counter - 1):offset * counter]
            a = ','.join(list_to_execute)
            code = '''var a = Args.a.split(',');
                      var i = 0;
                      var c = [];
                      while (i <25)
                      {
                          var groups = API.groups.get({'user_id':a[i]});
                          c.push(groups+{id:a[i]});
                          i= i+ 1;
                      }
                      return c;'''
            params = {'access_token': self.access_token, 'code': code, 'a': a, 'v': self.V}
            response = requests.get(url=f'{self.API}/execute', params=params)
            counter += 1
            print(f'Осталось обработать {len(search_list) - in_progress} человек')
            in_progress += offset
            time.sleep(0.3)
            resp = response.json()['response']
            for user_groups in resp:
                if type(user_groups) == dict:
                    id = user_groups.get('id')
                    a = set(user_groups.get('items'))
                    users_groups[id] = a
                for user in users_groups:
                    if len(users_groups[user].intersection(target_groups)) > 0:
                        people_with_mutual_groups.append(int(user))
        for user in search_list:
            if user['id'] in people_with_mutual_groups:
                user['weight'] += 4
        return search_list

    def get_top_10(self):
        searched_list = self.get_groups_by_execute()
        searched_list.sort(key=lambda searched_list: searched_list['weight'], reverse=True)
        return searched_list[:10]

    def get_top3_photos(self):
        users = self.get_top_10()
        photos = list()
        user_photos = dict()
        a = list()
        for user in users:
            params = {'owner_id': user['id'], 'access_token': self.access_token,
                      'album_id': 'profile', 'extended': 1, 'photo_sizes': 1, 'v': self.V}
            user_id = user['id']
            user.pop('can_access_closed')
            user.pop('is_closed')
            user.pop('track_code')
            user.pop('weight')
            if 'music' in user:
                user.pop('music')
            try:
                response = requests.get(f'{self.API}/photos.get', params=params).json()['response']
                photos.append(response)
                for photo in response['items']:
                    likes = photo['likes']['count']
                    for size in photo['sizes']:
                        if size['type'] == 'x':
                            url = size['url']
                            a.append({'likes': likes, 'url': url})
                    user_photos[user_id] = a
                    user['photo'] = user_photos[user['id']]
                a = []
            except KeyError:
                continue
        for element in user_photos:
            for_sort = user_photos[element]
            for_sort.sort(key=lambda for_sort: for_sort['likes'], reverse=True)
            for index in for_sort:
                a.append(index['url'])
            user_photos[element] = a[:3]
            a = []
        for user in users:
            if user['id'] in user_photos:
                user['photo'] = user_photos[user['id']]
        return users

    def write_json(self):
        json_dict = self.get_top3_photos()
        with open('most_common_people.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(json_dict, indent=4, ensure_ascii=False))
        return json_dict
    #
    # def connect_to_db(self):
    #     client = MongoClient("localhost", 27017)
    #     vkinder_db = client['admin']
    #     most_common_people_collection = vkinder_db['most_common_people_collection']
    #     return most_common_people_collection
    #
    # def write_to_db(self, filename):
    #     self.write_json()
    #     with open(filename, 'r', encoding='utf-8') as f:
    #         list_for_database = json.load(f)
    #     most_common_people_collection = self.connect_to_db()
    #     most_common_people_collection.insert_many(list_for_database)
    #     return list_for_database


class Database():
    def __init__(self):
        self.user = User(id)

    def connect_to_db(self):
        client = MongoClient("localhost", 27017)
        vkinder_db = client['admin']
        most_common_people_collection = vkinder_db['most_common_people_collection']
        return most_common_people_collection

    def write_to_db(self, filename):
        with open(filename, 'r', encoding='utf-8') as f:
            list_for_database = json.load(f)
        most_common_people_collection = self.connect_to_db()
        most_common_people_collection.insert_many(list_for_database)
        return list_for_database

    def get_items_from_db(self):
        db_collection = self.connect_to_db()
        db_users = list(db_collection.find())
        return db_users


if __name__ == "__main__":
    user_id = input("Введите id в формате idXXXXX, или screen name пользователя: ")
    user = User(user_id)
    db = Database()
    access_token = user.authorization()
    user.write_json()
    pprint(db.write_to_db('most_common_people.json'))
