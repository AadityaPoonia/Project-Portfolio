import random
import sqlite3
import pandas as pd

import argon2

class Database:
    
    @staticmethod
    def open():
        Database.db = sqlite3.connect("database/Database.db")
        Database.cursor = Database.db.cursor()
        
        Database.createTables()
        
        
    @staticmethod
    def select(query):
        Database.cursor.execute(query)
        
        return Database.cursor.fetchall()
    
    @staticmethod
    def selectOne(query):
        Database.cursor.execute(query)
        
        return Database.cursor.fetchone()
    
    @staticmethod
    def cud(query):
        Database.cursor.execute(query)
        
        Database.db.commit()
        return Database.cursor
        
    @staticmethod
    def default():
        
        key = argon2.PasswordHasher()
        hash = key.hash("password")
    
        Database.cursor.execute("DROP TABLE Users")
        Database.db.commit()
        
        Database.cursor.execute("DROP TABLE Locations")
        Database.db.commit()
        
        Database.cursor.execute("DROP TABLE Rents")
        Database.db.commit()
        
        Database.cursor.execute("DROP TABLE Vehicles")
        Database.db.commit()
        
        Database.createTables()
        Database.db.commit()
        
        Database.cursor.execute('INSERT INTO Locations(name, address, postcode) VALUES("Glasgow Kennedy street","214 Kennedy street","G4 0DB")')
        Database.cursor.execute('INSERT INTO Locations(name, address, postcode) VALUES("Paisley","39 Underwood Rd","PA3 1TQ")')
        Database.cursor.execute('INSERT INTO Locations(name, address, postcode) VALUES("Glasgow University Avenue","3 University Avenue","G12 8QQ")')
        Database.cursor.execute('INSERT INTO Locations(name, address, postcode) VALUES("Glasgow middle of nowhere","769 Shettleston Rd","G32 7NN")')
        Database.cursor.execute('INSERT INTO Locations(name, address, postcode) VALUES("Glasgow Argyle St","Argyle St","G3 8AG")')
        Database.cursor.execute('INSERT INTO Locations(name, address, postcode) VALUES("Kelvinbridge","130 Woodlands Rd","G3 6AB")')
        
        Database.cursor.execute('INSERT INTO Users(email, password, name, role, balance) VALUES("user1@ecs14.com",?,"Name1","user",10000)',[hash])
        Database.cursor.execute('INSERT INTO Users(email, password, name, role, balance) VALUES("user2@ecs14.com",?,"Name2","user",20000)',[hash])
        Database.cursor.execute('INSERT INTO Users(email, password, name, role, balance) VALUES("manager1@ecs14.com",?,"Name1","manager",10000)',[hash])
        Database.cursor.execute('INSERT INTO Users(email, password, name, role, balance) VALUES("op1@ecs14.com",?,"Name1","operator",10000)',[hash])
        
        types = ["scooter","bike","car","skateboard"]
        colors = ["blue","black","grey","red","white"]
        
        for i in range(1,7):
            for _ in range(random.randint(2,8)):    
                Database.cursor.execute('INSERT INTO Vehicles(type, color, fee, location_id, battery, status, damage) VALUES(?,?,?,?,?,"stationary","0")',(random.choice(types),random.choice(colors),random.randrange(50,250,50),i,random.randrange(10,100,5)))
        
        # Database.cursor.execute('INSERT INTO Rents VALUES(1,2,"DATE PU","DATE DO",1,2,0,0,0)')
        # Database.cursor.execute('INSERT INTO RENTS(user_id,vehicle_id,pickup_time,dropoff_time,pickup_location,dropoff_location,in_progress,damage,price) VALUES(1,2,"02::14::00","DATE DO",1,2,1,0,0)')
        # Database.cursor.execute('INSERT INTO Rents VALUES(1,2,"02::14::00","DATE DO",1,2,1,0,0)')
        
        Database.db.commit()
    
    @staticmethod    
    def createTables():
        #Users table
        Database.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Users(
                id integer PRIMARY KEY AUTOINCREMENT,
                email text UNIQUE,
                password text NOT NULL,
                name text NOT NULL,
                role text NOT NULL,
                balance real NOT NULL
            );
        """)
        
        #Location table
        Database.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Locations(
                id integer PRIMARY KEY AUTOINCREMENT,
                name text NOT NULL,
                address text NOT NULL,
                postcode text NOT NULL
            );
        """)
        
        #Vehicles table
        Database.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Vehicles(
                id integer PRIMARY KEY AUTOINCREMENT,
                type text NOT NULL,
                color text NOT NULL,
                fee real NOT NULL,
                location_id integer NOT NULL,
                battery integer NOT NULL,
                status text,
                damage integer NOT NULL,
                FOREIGN KEY(location_id) REFERENCES Locations(id)
            );
        """)
        
        
        #Rents table
        
        Database.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Rents(
                rent_id integer PRIMARY KEY AUTOINCREMENT,
                user_id integer NOT NULL,
                vehicle_id integer NOT NULL,
                pickup_date text NOT NULL,
                pickup_time text NOT NULL,
                dropoff_time text,
                pickup_location integer NOT NULL,
                dropoff_location integer,
                in_progress integer NOT NULL,
                damage integer NOT NULL,
                price real NOT NULL,
                FOREIGN KEY(pickup_location) REFERENCES Locations(id)
                FOREIGN KEY(dropoff_location) REFERENCES Locations(id)
            );
        """)
        Database.db.commit()
        
    @staticmethod    
    def close():
        Database.db.close()

    @staticmethod
    def dfTest(query):
        return pd.read_sql_query(query,Database.db)
    
        
    