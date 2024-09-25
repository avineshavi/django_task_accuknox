To up the frist we need to follow some steps:

Need to check that docker-compose is installed in your local machine if not installed need to install docker-compose steps to install docker and docker compose

Then after successful install of docker you need to enter the following commands

command 1 - ```docker-compose up --build```

Afetr the docker-compose up please run these commands given below in a new terminal tab with same path as the docker run

    command 1.1 - ```docker exec -it social_network_db_1 bash```

    command 1.2 - ```psql -U postgres -d social_network```

    command 1.3 - ```CREATE EXTENSION IF NOT EXISTS pg_trgm;```

Additionally I have aaded a json foemat data for signup users file name - ```registration_users_list.txt```

Postman collections are added file name - ```social_network.postman_collection.json```

I have added a postman_environment to set the access token dynamically, please add the base_url to the environment after importing the environment file

Example - ```{{base_url}}/api/login/``` the base_url is need to give in the environment after exporting the file in to postman ```social_network.postman_environment.json``` like set the ```base_url current value like "http://127.0.0.1:8000"``` an the ```access_token``` then the access token is taken as dynamically

For ```receiver_id``` of friend request ```send``` ids means the primary key of ```register_user table```

For ```friend_request_id``` of friend request ```accept/reject``` ids means the primary key of ```FriendRequest table```

For User ```bolcking/unblocking``` block_user_id means the id from  ```register_user``` table
