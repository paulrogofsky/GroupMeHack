__author__ = 'Paul'

import cherrypy
from pystache import Renderer
import getter

# get various modules from getter module so we are not double-importing
datetime = getter.datetime
loader = getter.loader
os = getter.os
csv = getter.csv
renderer = Renderer()

# below is the Root class for the Server I am running (it is the controller)
class Server(object):
    @cherrypy.expose
    def index(self, group = None, user = None, start_date = None, end_date = None, message_contains = None, favorited_by = None, pictures_only = '', page_num = 0):
        """
        Process an 'index' GET request
            -- deals with getting messages for user and processing if he/she is logged in or not
            -- below parameters are querystrings passed in by user upon a search of messages
        :param str group: The group id the user wants to get messages for
        :param str user: The user id the user wants to get messages for
        :param str start_date: The start date to get messages for
        :param str end_date: The end date to get messages for
        :param str message_contains: The string to search messages for
        :param str favorited_by: The user id the user wants to search who favorited for
        :param str pictures_only: Indicator if 'on' of whether user wants messages with pictures only
        :param str page_num: The page number the user wants to navigate to
        :return str: The string response text of the request
        """
        # the mustache template to populate and send as a response
        # if there is not access_token in the session, then we are logged in
        if 'access_token' not in cherrypy.session:
            # if not logged in return blank screen with login message
            return renderer.render_path(
                os.path.join('front_end', 'index.html'),
                {
                    'messages': [],
                    'users': [],
                    'pages': [],
                    'logged_in': False,
                    'groups': []
                }
            )
        # if group is passed in as a parameter-> make sure we indicate it in the session
        if group:
            cherrypy.session['group'] = group
        # if group is not passed in as a paremter-> get it from the session
        if not group and 'group' in cherrypy.session:
            group = cherrypy.session['group']
        # get all groups
        groups = getter.get_groups(cherrypy.session['access_token'])
        # if we still don't have a group-> let's just populate it with the first group in the list
        if not group:
            group = groups[0]['id']
        # user must have access to Group, as indicated by what groups he is
        user_access_to_group = False
        # indicate in groups which group is selected for templating/dropdown purposes
        for gr in groups:
            if gr['id'] == group:
                user_access_to_group = True
                gr['group_inp'] = True
                break
        if not user_access_to_group:
            return renderer.render_path(
                os.path.join('front_end', 'index.html'),
                {
                    'messages': [],
                    'users': [],
                    'pages': [],
                    'logged_in': False,
                    'groups': []
                }
            )
        if ('loaded%s' % group) not in cherrypy.session:
            cherrypy.session['loaded%s' % group ] = 'loaded'
            # let's load in messages to csv from GroupMe below
            message_counts = loader.handle_messages_to_csv(cherrypy.session['access_token'], group)
            # let's load in messages from csv to MongoDB
            messages_filename = os.path.join('data_files', 'messages', '%s.csv' % group)
            with open(messages_filename, 'rb') as messages_file:
                csv_messages = list(csv.DictReader(messages_file, delimiter = ','))
                new_messages = csv_messages[: message_counts['recent_messages']] + csv_messages[message_counts['stored_messages']: message_counts['historical_messages']]
                loader.load_to_mongo(cherrypy.session['access_token'], 'messages', group, getter.session.post, new_messages)
        # process parameters below-> if pictures_only is 'on', then it is True
        pictures_only = True if pictures_only == 'on' else False
        # if following string inputs are empty strings, then we want them to be None for processing when getting messages
        user, start_date, end_date, message_contains, favorited_by = map(
            lambda param: None if param == '' else param,
            [user, start_date, end_date, message_contains, favorited_by]
        )
        # convert date strings to date datetimes, or if the user did not input them-> then they are None
        start_date_d, end_date_d = [
            (datetime.strptime(date_elem, '%Y-%m-%d') if date_elem else None) for date_elem in [start_date, end_date]
        ]
        # once parameters set up-> now we can get messages
        messages = getter.get_messages(
            group,
            int(page_num) * 20,
            20,
            user,
            start_date_d,
            end_date_d,
            message_contains,
            int(favorited_by) if favorited_by else None,
            pictures_only
        )
        # get users and populate which ones are selected for favorited and user in Search paras to populate dropdowns
        users = getter.get_users(group)
        for user_u in users:
            if user_u['id'] == favorited_by:
                user_u['fav_inp'] = True
            if user_u['id'] == user:
                user_u['user_inp'] = True
        # organized_users is an id->name key-value map of users so we can see who liked messages
        organized_users = {user_u['id']: user_u['name'] for user_u in users}
        for message in messages['messages']:
            # get pictures into list as opposed to space-separated string
            message['pictures'] = [] if not len(message['pictures']) else message['pictures'].split(' ')
            # get each person's name that liked a message, not just their id (also get rid of space separated favorited variable)
            new_favorites_organized = []
            for favorite_person_id in ([] if not len(message['favorited']) else message['favorited'].split(' ')):
                new_favorites_organized.append({'id': favorite_person_id, 'name': organized_users[favorite_person_id] if favorite_person_id in organized_users else 'UNKNOWN'})
            message['favorited'] = new_favorites_organized
            # convert date datetime from timestamp to date for user usability
            try:
                message['datetime'] = datetime.utcfromtimestamp(float(message['datetime'])).strftime('%m/%d/%Y at %X')
            except ValueError:
                print message['datetime']
        # let's get pagination below
        pages = Server.get_pagination_details(messages['count'], int(page_num), 20)
        # populate template with the data below and render it
        return renderer.render_path(
            os.path.join('front_end', 'index.html'),
            {
                'messages': messages['messages'],
                'users': users,
                'pages': pages,
                'groups': groups,
                'end_date': end_date,
                'start_date': start_date,
                'pictures_only': pictures_only,
                'message_contains': '' if not message_contains else message_contains,
                'logged_in': True
            }
        )


    @cherrypy.expose
    def login(self):
        """
        Process 'login' GET request-> just a redirect to GroupMe authorization client
        :return: Nothing, void function
        """
        raise cherrypy.HTTPRedirect(
            'https://oauth.groupme.com/oauth/authorize?client_id=8SvGBpekTKCh51Mk8NQ42lFVIyjyXleLmPmW3iPBMhMbjid9'
        )


    @cherrypy.expose
    def post_login(self, access_token = ''):
        """
        Process the 'post_login' GET request
            -- GroupMe auth redirects to this endpoint upon successful Login
        :param str access_token:
        :return:
        """
        # store in session the access_token yielded for the user
        cherrypy.session['access_token'] = access_token
        # load groups so we know which groups the user has access o
        loader.load_groups_to_csv(access_token)
        # then let's redirect to the 'index' route
        raise cherrypy.HTTPRedirect('/index')

    @staticmethod
    def get_pagination_details(num_records, page_num = 0, num_rows = 20):
        """
        Get which pages to show on the screen at a given time
        :param int num_records: The number of records that a user has chosen to want to view
        :param int page_num: The page number that the user is at
        :param int num_rows: The number of rows on the page
        :return list: The details we need for pagination (Back button, Forward button, First, Last based on where user is)
        """
        pages = []
        # if no records-> then we are not returning any pages
        if not num_records:
            return pages
        num_pages_possible = int(num_records / num_rows)
        # if the page number is greater than that which is possible, then let's go to the 0th page
        if num_pages_possible < page_num:
            page_num = 0
        # if the page number is not 0-> then let's show a First and Previous button
        if page_num:
            pages.append({'label': 'First', 'page_num': 0})
            pages.append({'label': 'Previous', 'page_num': page_num - 10 if page_num > 9 else 0})
        # lowest_page_num can't be less than 0 or greater than the maximum number of pages possible + 10 (always want to show 10 page options)
        lowest_page_num = num_pages_possible - 10 if num_pages_possible < page_num + 10 else page_num
        lowest_page_num = 0 if lowest_page_num < 0 else lowest_page_num
        # we will show 10 pages below-> the one selected will be highlighted with a 'selected' key
        for number in range(lowest_page_num, num_pages_possible if num_pages_possible - page_num < 10 else page_num + 10):
            page = {'label': number + 1, 'page_num': number}
            if number == page_num:
                page['selected'] = True
            pages.append(page)
        # if we aren't at the end-> let's show an option for the Next ten pages and the Last page
        if num_pages_possible - page_num > 9:
            pages.append({'label': 'Next', 'page_num': page_num + 10 if page_num + 10 < num_pages_possible else num_pages_possible})
            pages.append({'label': 'Last', 'page_num': num_pages_possible})
        return pages


    @cherrypy.expose
    def pictures(self, group = None):
        """
        Process a 'pictures' GET request
            - Get all pictures for a certain group
        :param str group: The group to get the pictures for
        :return str: The string response text of the request
        """
        if not group:
            raise cherrypy.HTTPRedirect('/index')
        pictures = getter.get_pictures(group)
        formatted_pictures = []
        for num in range(0, len(pictures)):
            if num % 10 == 0:
                formatted_pictures.append({
                    'row_pics': []
                })
            formatted_pictures[-1]['row_pics'].append(pictures[num])
        return renderer.render_path(
            os.path.join('front_end', 'pictures.html'),
            {
                'pics': formatted_pictures
            }
        )



if __name__ == '__main__':
    # configure the server and start it up below
    cherrypy.config.update(os.path.join('log_files', 'server.conf'))
    cherrypy.quickstart(Server())
