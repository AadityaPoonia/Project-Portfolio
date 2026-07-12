from database.database import Database

"""
    Python executable to revert the database back to its default state and output its values, serves initializing and testing purposes
"""

if __name__ == "__main__":
    Database.open()
    Database.default()
    
    print("******************************")
    print("Locations:")
    for x in Database.select("SELECT * FROM Locations"):
        print(x)
    print("******************************")
    print("Users:")
    for x in Database.select("SELECT * FROM Users"):
        print(x)
    print("******************************")
    print("Vehicles:")
    for x in Database.select("SELECT * FROM Vehicles"):
        print(x)    
    print("******************************")
    print("Rents:")
    for x in Database.select("SELECT * FROM Rents"):
        print(x)
    print("******************************")
    
    Database.close()