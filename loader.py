__author__ = 'Paul'

import os
import requests
from requests.adapters import HTTPAdapter
import csv
import argparse
import json

# The Mongo Lab settings are below
mongo_lab_settings = {
    'email': 'progo94@aol.com',
    'admin_name': 'flockteam',
    'password': 'flockbros1',
    'database_name': 'groupmehack',
    'username': 'progo|Paul Rogofsky',
    'user_name': 'paul',
    'user_password': 'flowers12',
    'api': 'SM1eOEebZMzrZfmSb7u3LKXv7ZU0YUbY'
}

# start up request session below to save cookies, if faster for GroupMe
session = requests.Session()
session.mount('https://', HTTPAdapter(max_retries = 3))

def ascii(x):
    """
    Converts x to an ascii string- specifically important for emojis/other items in text as CSV reader only takes ascii chars
    :param x: parameter to be converted (usually a unicode string)
    :return: an ascii string
    """
    return '' if x is None else x.encode('ascii','ignore') if isinstance(x,unicode) else str(x.decode('ascii','ignore'))

def load_groups_to_csv(token):
    """
    Load from GroupMe API into a CSV file the id and name of all the groups you are in
    :param str token: token to access Group Me API with
    :return: Nothing, void function
    """
    # remove file path, and then recreate file (no overwriting)
    filename = os.path.join('data_files', 'groups', '%s.csv' % token)
    if os.path.exists(filename):
        os.remove(filename)
    with open(filename, 'wb') as groups_file:
        csv_writer = csv.writer(groups_file, delimiter = ',')
        # get data from GroupMe API- write it to CSV
        groups_request = session.get('https://api.groupme.com/v3/groups', params = {'token': token})
        groups_data = groups_request.json()['response']
        csv_writer.writerow(['id', 'name', 'message_count'])
        for group in groups_data:
            csv_writer.writerow([group['id'], ascii(group['name']), group['messages']['count']])

def get_users(users_filename):
    """
    Get groups from the CSV file
    :param str users_filename: The name of the groups file to get the groups from
    :return dict: Mapping of user ids to user names
    """
    users = {}
    if os.path.exists(users_filename):
        with open(users_filename, 'rb') as users_file:
            csv_users_reader = csv.DictReader(users_file, delimiter = ',')
            for row in csv_users_reader:
                users[row['id']] = row['name']
        os.remove(users_filename)
    return users

def request_messages_for_csv(message_writer, picture_writer, token, group_id, users, message_id, most_recent):
    """
    Get Messages from the GroupMe API and store the messages and pictures in the CSV and groups in the dictionary
    :param csv.DictWriter message_writer: csv file container to write messages to
    :param csv.DictWriter picture_writer: csv writer container to write pictures to
    :param str token: Access Token to group me api
    :param str group_id: Group id to get the messages from
    :param dict users: key-value pair dictionary of groups (ids to names map which we are updating)
    :param int message_id:
    :param bool most_recent: Indicator of whether we get the most
    :return int: Number of messages requested and received from GroupMe API
    """
    # update request parameters for GroupMe API- if most recent, get after message id; if not most recent, get before message id
    request_params = {'token': token, 'limit': 100}
    if message_id and most_recent:
        request_params['after_id'] = message_id
    elif message_id and not most_recent:
        request_params['before_id'] = message_id
    # error- can't get most recent if there is no message id-> which indicates we don't have any messages
    elif (not message_id) and most_recent:
        return 0
    messages_request = session.get('https://api.groupme.com/v3/groups/%s/messages' % group_id, params = request_params)
    # if we can't decode json, then there are no more messages to retrieve
    try:
        response_data = messages_request.json()['response']
    except ValueError:
        return 0
    # if no messages-> let's exit function
    if response_data['count'] == 0:
        return 0
    message_id = None
    for message in response_data['messages']:
        attachments = message['attachments']
        message_id = message['id']
        user_id = message['user_id']
        user_name = ascii(message['name'])
        # only add groups that are not there or we are loading a new name from the past (past names are better than current)
        if (user_id not in users) or (user_id in users and not most_recent):
            users[user_id] = user_name
        # load in pictures, and write them
        pictures = []
        for attach in attachments:
            if attach['type'] == 'image':
                pictures.append(ascii(attach['url']))
                picture_writer.writerow({'url': attach['url'], 'message_id': message_id})
        # notice that favorited and pictures are going to be space-delimited fields in csv file (user ids for favorite and urls for pics)
        message_row = {
            'id': message_id,
            'user_id': user_id,
            'user_name': user_name,
            'text': ascii(message['text']),
            'datetime': message['created_at'],
            'favorited': ' '.join(message['favorited_by']),
            'pictures': ' '.join(pictures)
        }
        message_writer.writerow(message_row)
    message_count = len(response_data['messages'])
    # indicator that there are more messages-> number of messages > 5 and there are message_id != None (preset)
    if message_id and message_count > 5:
        # add new messages from this GroupMe request to the new messages from the next request
        message_count += request_messages_for_csv(message_writer, picture_writer, token, group_id, users, message_id, most_recent)
    return message_count


def handle_messages_to_csv(token, group_id):
    """
    Instead of overloading the GroupMe API, we are going to intelligently load all messages not already loaded into the CSV through this method
    :param str token: The token to access the GroupMe api with
    :param str group_id: The id of the group that the user wants to get messages for
    :return dict: Message counts of messages just loaded and already stored in csv
    """
    message_counts = {
        'recent_messages': 0,
        'stored_messages': 0,
        'historical_messages': 0
    }
    # get file names below, Note: we are writing to temp files then renaming them at the end of the function
    messages_filename = os.path.join('data_files', 'messages', '%s.csv' % group_id)
    pictures_filename = os.path.join('data_files', 'pictures', '%s.csv' % group_id)
    temp_messages_filename = os.path.join('data_files', 'temp_messages.csv')
    temp_pictures_filename = os.path.join('data_files', 'temp_pictures.csv')
    users_filename = os.path.join('data_files', 'members', '%s.csv' % group_id)
    users = get_users(users_filename)
    # open up the files
    with open(temp_messages_filename , 'wb') as new_messages_file, open(temp_pictures_filename, 'wb') as new_pictures_file:
        # create the messages/pictures writers below (write header too)
        csv_messages_writer = csv.DictWriter(
            new_messages_file,
            fieldnames = ['id', 'user_id', 'user_name', 'text', 'datetime', 'favorited', 'pictures'],
            delimiter = ','
        )
        csv_messages_writer.writeheader()
        csv_pictures_writer = csv.DictWriter(new_pictures_file, fieldnames = ['url', 'message_id'], delimiter = ',')
        csv_pictures_writer.writeheader()
        # store the last message (or the most back in history) from previous read file in last_message
        last_message = None
        # check if there were old messages we have stored
        if os.path.exists(messages_filename):
            with open(messages_filename, 'rb') as old_messages_file:
                csv_messages_reader = csv.DictReader(old_messages_file, delimiter = ',')
                # most_recent only used for finding the first message in the csv reader
                most_recent = True
                old_message_count = 0
                for row in csv_messages_reader:
                    # the first message is the most recent one we got (we will keep it that way by searching for messages after the first message)
                    if most_recent:
                        message_counts['recent_messages'] = request_messages_for_csv(csv_messages_writer, csv_pictures_writer, token, group_id, users, row['id'], True)
                        most_recent = False
                    # then continue writing all the messages found in the body
                    csv_messages_writer.writerow(row)
                    old_message_count += 1
                    last_message = row
                message_counts['stored_messages'] = old_message_count
                # once done reading old file, let's delete it
            os.remove(messages_filename)
        # just write everything to the csv pictures, nothing fancy here (previous function loads more recent pictures than body of csv)
        if os.path.exists(pictures_filename):
            with open(pictures_filename, 'rb') as old_pictures_file:
                csv_pictures_reader = csv.DictReader(old_pictures_file, delimiter = ',')
                csv_pictures_writer.writerows(csv_pictures_reader)
            # once done reading old file, let's delete it
            os.remove(pictures_filename)
        # lastly, we try to load all messages that occurred before the last message (most distant in past)
        message_counts['historical_messages'] = request_messages_for_csv(
            csv_messages_writer,
            csv_pictures_writer,
            token,
            group_id,
            users,
            last_message['id'] if last_message else None,
            False
        )
    # rename files when we are done writing to them, remove old files (and since they are closed)
    os.rename(temp_messages_filename, messages_filename)
    os.rename(temp_pictures_filename, pictures_filename)
    # rewrite all groups that we collected from the messages data to groups file
    with open(users_filename, 'wb') as users_file:
        csv_users_writer = csv.DictWriter(users_file, fieldnames = ['id', 'name'])
        csv_users_writer.writeheader()
        for user_id, user_name in users.iteritems():
            csv_users_writer.writerow({'id': user_id, 'name': user_name})
    return message_counts


def load_to_mongo (token, collection, group_id, request_method, data):
    """
    Loads data to a MongoDB collection, either inserts or puts data based on the request_method
    :param str token: The access token that identifies the user
    :param str collection: The name of the Collection we are uploading to Mongo ('messages', 'pictures', 'users', 'groups')
    :param str group_id: The group id to upload to Mongo
    :param function request_method: Either requests.post for inserting data or requests.put for putting data into db
    :param list data: The data to insert/put into the database
    :return: Nothing, void function
    """
    # just dump csv into request-> and we are able to insert into mongo lab
    collection_request = request_method(
        'https://api.mongolab.com/api/1/databases/groupmehack/collections/%s%s?apiKey=%s' % (
            group_id if group_id else token,
            collection,
            mongo_lab_settings['api']
        ),
        data = json.dumps(data),
        headers = {'Content-Type': 'application/json'}
    )
    collection_response = collection_request.json()
    # 'n' indicates the number of rows we inserted into MongoDB- if present we did well
    if 'n' in collection_response and collection_response['n'] > 0:
        print 'Updated %s records to Mongo from CSV of Collection %s%s' % (
            collection_response['n'],
            collection,
            (', Group number %s' % group_id) if group_id else ''
        )
    else:
        print 'unsuccessful load to Mongo of Collection %s%s' % (
            collection,
            ', Group number, %s' % (group_id if group_id else '')
        )


def load_csv_to_mongo (token, collection, group_id):
    """
    Load Data saved locally in CSV into MongoLab
    :param str token: The access token that identifies the user
    :param str collection: The name of the Collection we are uploading to Mongo ('Messages', 'Pictures', 'Users', 'Groups')
    :param str group_id: The group id to upload to Mongo
    :return: Nothing, void function
    """
    file_path = os.path.join('data_files', collection, '%s.csv' % (group_id if group_id else token))
    # only upload if file exists and we have CSV data
    if os.path.exists(file_path):
        with open(file_path, 'rb') as collection_file:
            csv_collection_reader = csv.DictReader(collection_file, delimiter = ',')
            load_to_mongo(token, collection, group_id, session.put, list(csv_collection_reader))


if __name__ == '__main__':
    # ensure data_files folder exists for storing data
    if not os.path.exists('data_files'):
        os.makedirs('data_files')
    for dir_name in ['groups', 'messages', 'members', 'pictures']:
        if not os.path.exists(os.path.join('data_files', dir_name)):
            os.makedirs(dir_name)
    # build argument parser below for interacting with GroupMe API
    # two main functions-> loading from GroupMe to CSV and from CSV to Mongo
    parser = argparse.ArgumentParser(description='Interact with the GroupMe Bulk Loading Program')
    parser.add_argument('access_token', type = str, help = 'Access Token to access the GroupMe API with')
    parser.add_argument('--groupsCSV', action = 'store_true', default = False, help = 'Add groups to CSV from GroupMe')
    parser.add_argument('--messagesCSV', type = int, default = -1, help = 'Add messages to CSV from GroupMe of the group id you pass in')
    parser.add_argument('--groupsMongo', action = 'store_true', default = False, help = 'Add groups to MongoLab from GroupMe using CSV data')
    parser.add_argument('--messagesMongo', type = int, default = -1, help = 'Add messages to MongoLab using CSV data of the group id you pass in')
    args = parser.parse_args()
    if args.groupsCSV:
        load_groups_to_csv(args.access_token)
        print 'Successful storage of groups in CSV'
    if args.messagesCSV != -1:
        handle_messages_to_csv(args.access_token, args.messagesCSV)
        print 'Successful local storage of messages in CSV, Group number %s' % args.messagesCSV
    if args.groupsMongo:
        load_csv_to_mongo(args.access_token, 'groups', '')
    if args.messagesMongo:
        for collection_name in ['messages', 'pictures', 'members']:
            load_csv_to_mongo(args.access_token, collection_name, args.messagesMongo)
    # session.get('https://api.groupme.com/v3/groups/2947318/messages', params={'before_id': 137607368696683000, 'limit': 100, 'token': 'fbac6d40180b0133df9626b3b369444a'})
    # todo: handle unknowns
