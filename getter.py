__author__ = 'Paul'

import loader
import json
from datetime import datetime
import calendar

# load in session and settings from loader so we don't double import
session = loader.session
mongo_lab_settings = loader.mongo_lab_settings
os = loader.os
csv = loader.csv


def get_users(group_id, db = False):
    """
    Get the users for a given group
    :param str group_id: The group id to search users for
    :param bool db: The indicator of whether to get users from db or from csv stored locally (if false)
    :return list: List of users- has their id and name information
    """
    if db:
        users_request = session.get(
            'https://api.mongolab.com/api/1/databases/groupmehack/collections/%smembers' % group_id,
            params = {'apiKey': mongo_lab_settings['api'], 's': json.dumps({'name': 1})}
        )
        return users_request.json()
    # find file that contains users-> then parse the csv and return json list
    users_filename = os.path.join('data_files', 'members', '%s.csv' % group_id)
    if os.path.exists(users_filename):
        with open(users_filename, 'rb') as groups_file:
            csv_reader = csv.DictReader(groups_file, fieldnames = ['id', 'name'], delimiter = ',')
            # don't include header in list of users (therefore exclude first element in array)
            return list(csv_reader)[1:]
    # if no file-> return none
    return None


def get_groups(token, db = False):
    """
    Get the groups associated with the user (unique access token identifier)
    :param bool db: The indicator of whether to get users from db or from csv stored locally (if false)
    :param str token: GroupMe access token associated with the user
    :return list: List of groups that user is in
    """
    if db:
        users_request = session.get(
            'https://api.mongolab.com/api/1/databases/groupmehack/collections/%sgroups' % token,
            params = {'apiKey': mongo_lab_settings['api'], 's': json.dumps({'name': 1})}
        )
        return users_request.json()
    # find file that contains users-> then parse the csv and return json lis
    groups_filename = os.path.join('data_files', 'groups', '%s.csv' % token)
    if os.path.exists(groups_filename):
        with open(groups_filename, 'rb') as groups_file:
            csv_reader = csv.DictReader(groups_file, fieldnames = ['id', 'name', 'message_count'], delimiter = ',')
            # don't include header in list of groups (therefore exclude first element in array)
            return list(csv_reader)[1:]
    # if no file-> then return None as indicator
    return None

def get_pictures(group_id, db = False):
    """
    Get the pictures for a given group
    :param str group_id: The group id to search users for
    :param bool db: The indicator of whether to get users from db or from csv stored locally (if false)
    :return list: List of pictures- has which message it corresponds to and the url
    """
    if db:
        users_request = session.get(
            'https://api.mongolab.com/api/1/databases/groupmehack/collections/%spictures' % group_id,
            params = {'apiKey': mongo_lab_settings['api'], 's': json.dumps({'name': 1})}
        )
        return users_request.json()
    # find file that contains users-> then parse the csv and return json list
    users_filename = os.path.join('data_files', 'pictures', '%s.csv' % group_id)
    if os.path.exists(users_filename):
        with open(users_filename, 'rb') as groups_file:
            csv_reader = csv.DictReader(groups_file, fieldnames = ['url', 'message_id'], delimiter = ',')
            # don't include header in list of users (therefore exclude first element in array)
            return list(csv_reader)[1:]
    # if no file-> return none
    return None

def get_messages(group_id, offset = 0, limit = 20, user_id = None, start_date = None, end_date = None, message_contains = None, favorited_by = None, pictures_only = False):
    """
    Get the messages for a group given various possible search parameters below
    :param string group_id: The group id to get messages for
    :param int offset: The offset of the messages we are getting
    :param int limit: The limit of the number of messages we are getting (None if we want all messages)
    :param list user_id: The list of users to get messages for
    :param datetime start_date: The first day to get messages for
    :param datetime end_date: The last day to get messages for
    :param str message_contains: The phrase in the message to look for
    :param int favorited_by: The list of people to get the favorited for
    :param bool pictures_only: To get messages with pictures only
    :return dict: A JSON object that contains all the messages for the given search parameters, and the number of records
    """
    # messages is what we will return
    messages = []
    mongo_query_params = {}
    # below we will store the various function params and turn them into appropriate mongoDB parameters
    if user_id:
        mongo_query_params['user_id'] = user_id
    if start_date and not end_date:
        # get only dates above start_date if no end date
        mongo_query_params['datetime'] = {'$gte': '%s' % calendar.timegm(start_date.timetuple())}
    elif end_date and start_date:
        # get dates between start and end date
        mongo_query_params['datetime'] = {
            '$gte': '%s' % calendar.timegm(start_date.timetuple()),
            '$lte': '%s' % calendar.timegm(end_date.timetuple())
        }
    elif end_date and not start_date:
        # get dates before end date if no start date
        mongo_query_params['datetime'] = {'$lte': '%s' % calendar.timegm(end_date.timetuple())}
    else:
        mongo_query_params['datetime'] = {'$gte': "0"}
    if message_contains:
        mongo_query_params['text'] = {'$regex': message_contains}
    if favorited_by:
        mongo_query_params['favorited'] = {'$regex': '%s' % favorited_by}
    if pictures_only:
        mongo_query_params['pictures'] = {'$ne': ''}
    # the max amount of data we can get from mongo is 1000 rows
    limit_mongo_fetch = limit if limit and limit < 1000 else 1000
    url = 'https://api.mongolab.com/api/1/databases/groupmehack/collections/%smessages' % group_id
    # let's capture the total amount of records we can get without limiting ourself-> this is needed for pagination
    count_message_request = session.get(
        url,
        params = {'apiKey': mongo_lab_settings['api'], 'q': json.dumps(mongo_query_params), 'c': True}
    )
    # offset must be less than offset + limit (increment offset by number of records received)
    while not limit or offset < offset + limit:
        # request data from MongoDB and then add to all the messages we will send back, sort by datetime and limit/offset messages
        message_request = session.get(
            url,
            params = {
                'apiKey': mongo_lab_settings['api'],
                'q': json.dumps(mongo_query_params),
                'sk': offset,
                'l': limit_mongo_fetch,
                's': '{"datetime": -1}'
            }
        )
        curr_messages = message_request.json()
        messages += curr_messages
        # if the number of messages we received is less than 1000, then we automatically know we got everything we needed to and there will be no more data
        num_messages = len(curr_messages)
        if num_messages < 1000:
            break
        # increment offset by number of messages received from db
        offset += num_messages
    # return messages and corresponding no-limit count of query
    return {'messages': messages, 'count': count_message_request.json()}
