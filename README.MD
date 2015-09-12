As it currently stands, GroupMe is not a very nostalgic messaging platform. No messaging platform really is.
The goal of this app is to allow users to easily go back in time and search what they are looking for. I know,
for example, that I want to go back and see funny messages by a very lude individual or go back and see a funny
conversation that my frends had 2 years ago. With the GroupMe app, you have to keep scrolling. With their
highly protected API, you can't isolate messages by users, check messages by date, view messages someone liked,
or check messages by text content. Additionally, the pictures worth 1000 messages should be viewed as a photo album.
In the GroupMe app, you can pretty much load only 20 pictures at a time. Therefore, I wanted to create a page where you
can view all your pictures using the GroupMe CDN. These are all valuable features that all messaging apps should offer.

Having this in mind, since GroupMe is a platform that I commonly use in college, I wanted to create a web applicaton
to offer these features. To accomplish this, I needed to retrieve all messages from GroupMe through a 'loader' file.
Once the messages are retrieved, I needed to store them, and since I am in college and not paying for database storage
or offering my own computer up as storage, I stored messages in CSV files. However, CSV files have no relational database
capabilities, so I used MongoLab to store data and perform queries (which are in the 'getter' file). The CSV files
are necessary since MongoLab's storage is very limited on a free account. Updating/inserting messages into MongoLab
is an important problem that needs to be solved in this app. Lastly, the web application is served through a CherryPy
server, which was very simple to setup. A user must login through GroupMe and can only view group data he is a member
of.