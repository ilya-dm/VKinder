from pprint import pprint
import requests
import time
import json
from data import app_id, vk_api
from datetime import datetime
import re
from pandas import json_normalize
from pymongo import MongoClient

class User:
    def __init__(self, id):
        self.id = id
        self.access_token = self.authorization()
        self.delta = 4
        self.V = '5.103'
        self.API = "https://api.vk.com/method"
    def authorization(self):
        url = f'https://oauth.vk.com/authorize?client_id={app_id}&display=popup&redirect_uri=https://oauth.vk.com' \
              f'/blank.html&scope=friends&response_type=token&v=5.103 '
        print('Чтобы получить токен для авторизации, перейдите по ссылке: ')
        print(url)
        access_token = input("Введите токен: ")
        return access_token

    def get_groups(self):
        group_list = list()
        group_set = set()
        params = {'access_token': self.access_token, 'user_id': self.resolveScreenName(self.id), 'v': self.V,
                  'extended': 1, 'fields': ['members_count']}
        response = requests.get(f'{self.API}/groups.get', params=params).json()['response']
        if response is not None:
            items = response.get('items')
            for item in items:
                try:
                    description = {'gid': item['id'], 'name': item['name'], 'members_count': item['members_count']}
                    group_list.append(description)
                    group_set.add(item['id'])
                except KeyError:
                    continue
        return group_set

    def resolveScreenName(self, screen_name):
        params = {'access_token': self.access_token, 'screen_name': screen_name, 'v': self.V}
        response = requests.get(f"{self.API}/utils.resolveScreenName", params=params).json()['response']
        ID = response['object_id']
        return ID

    def getUserInfo(self):
        params = {'access_token': self.access_token, 'user_ids': self.resolveScreenName(self.id), 'fields':
            'city ,sex, bdate, music', 'v': self.V}
        response = requests.get(f"{self.API}/users.get", params=params).json()['response'][0]
        for data in response:
            if response[data] == '':
                new_data = input(f"Заполните поле {data}: ")
                response[data] = new_data
        if 'city' not in response:
            city = input("Введите город: ")
            params = {'access_token': self.access_token, 'country_id': 1, 'q': city, 'v': self.V}
            city_request = requests.get(f"{self.API}/database.getCities", params=params).json()['response']
            city_request = city_request['items'][0]
            response['city'] = city_request
        if 'bdate' not in response:
            bdate = input('Введите дату рождения в формате дд.мм.гггг: ')
            response['bdate'] = bdate
        if len(response['bdate']) < 8:
            response['bdate'] += '.' + input('Введите год рождения:')
        return response

    def search_users_by_filter(self):
        target = self.getUserInfo()
        common_music = list()
        db_list = list()
        if target['sex'] == 2:
            filter_sex = 1
        elif target['sex'] == 1:
            filter_sex = 2
        filter_city = target['city']['id']
        today = datetime.strptime(datetime.today().strftime("%d.%m.%Y"), "%d.%m.%Y")
        bdate = datetime.strptime(target['bdate'], "%d.%m.%Y")

        db_collection = self.connect_to_db()
        db_users = list(db_collection.find({}, {'id': 1}))
        for index in db_users:
            db_list.append(index['id'])
        filter_age_min = int((today - bdate).days / 365) - self.delta
        filter_age_max = int((today - bdate).days / 365) + self.delta
        params = {'access_token': self.access_token, 'count': 1000, 'offset': len(db_users), 'city': filter_city,
                  'sex': filter_sex, 'status': 6, 'age_from': filter_age_min,
                  'age_to': filter_age_max, 'has_photo': 1, 'fields': 'music', 'v': self.V}
        searched_users = requests.get(f"{self.API}/users.search", params=params).json()['response']['items']
        for index in range(len(searched_users)-1, -1, -1):
            searched_users[index]['weight'] = 0
            if searched_users[index]['id'] in db_list:
                searched_users.remove(searched_users[index])
        music_filter = target['music']
        if ',' in music_filter:
            music_filter = music_filter.split(',')
        for user in searched_users:
            if type(music_filter) == list:
                try:
                    for element in music_filter:
                        a = re.search(re.compile(element, re.IGNORECASE), user['music'])
                        common_music.append(a)
                    if len(common_music) > 0:
                        user['weight'] += 3
                        common_music = []
                except KeyError:
                    continue
            else:
                try:
                    a = re.search(re.compile(music_filter, re.IGNORECASE), user['music'])
                    common_music.append(a)
                    if len(common_music) > 0:
                        user['weight'] += 3
                        common_music = []
                except KeyError:
                    continue
        return searched_users

    def mutual_friends_filter(self):
        target_uids_lst = []
        searched_users = self.search_users_by_filter()
        offset = 0
        people_with_mutual = list()
        for user in searched_users:
            user_id = str(user["id"])
            target_uids_lst.append(user_id)
        for index in range(100, len(target_uids_lst), 100):
            user_ids = ','.join(target_uids_lst[offset: index - 1])
            offset += 100
            response = requests.get(
                "https://api.vk.com/method/friends.getMutual",
                params={
                    "access_token": self.access_token,
                    "v": "5.103",
                    "source_uid": self.resolveScreenName(self.id),
                    "target_uids": user_ids,
                }
            )
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
        most_common = list()
        photos = list()
        searced_list = self.get_groups_by_execute()
        df = json_normalize(searced_list)
        df = df.sort_values(by="weight", ascending=False).head(10)
        df = df['id'].to_list()

        for user in searced_list:
            if user['id'] in df:
                most_common.append(user)
        for user in most_common:
            user['link'] = 'https://vk.com/id' + str(user['id'])
        return most_common

    def get_top3_photos(self):
        users = self.get_top_10()
        photos = list()
        user_photos = dict()
        a = list()
        for user in users:
            params = {'owner_id': user['id'], 'access_token': self.access_token,
                      'album_id': 'profile', 'extended': 1, 'photo_sizes': 1, 'v': self.V}
            user_id = user['id']
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
                a = []
            except KeyError:
                continue
        for element in user_photos:
            for_sort = user_photos[element]
            for_sort.sort(key=lambda for_sort: for_sort['likes'], reverse= True)
            for index in for_sort:
               a.append(index['url'])
            user_photos[element] = a[:3]
            a = []
        for user in users:
            if user['id'] in user_photos:
                user['photo'] = user_photos[user['id']]
            user.pop('can_access_closed')
            user.pop('is_closed')
            user.pop('track_code')
            user.pop('weight')
            try:
                user.pop('music')
            except KeyError:
                continue
        return users
    def write_json(self):
        json_dict = self.get_top3_photos()
        with open('most_common_people.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(json_dict, indent=4, ensure_ascii=False))
        return json_dict

    def connect_to_db(self):
        client = MongoClient("localhost", 27017)
        vkinder_db = client['admin']
        most_common_people_collection = vkinder_db['most_common_people_collection']
        return most_common_people_collection

    def write_to_db(self, filename):
        self.write_json()
        with open(filename, 'r', encoding='utf-8') as f:
            list_for_database = json.load(f)
        most_common_people_collection = self.connect_to_db()
        most_common_people_collection.insert_many(list_for_database)
        return list_for_database

if __name__ == "__main__":

    user_id = input("Введите id в формате idXXXXX, или screen name пользователя: ")
    user = User(user_id)
    pprint(user.write_to_db('most_common_people.json'))

