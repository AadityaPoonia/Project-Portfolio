import tkinter as tk
from tkinter import messagebox

# Importing different pages listed under Pages folder
from Pages.login import Login
from Pages.signup import Signup
from Pages.client import Client
from Pages.renting import Renting
from Pages.operator import Operator
from database.database import Database
from Pages.manager import Manager
from Pages.operator import Operator
#add more pages if needed

class MainApp(tk.Tk):

    """
    MainApp class is the main engine class of the entire application,
    managing pages, the authenticated user, and the outer layer of business
    logic 
    """    
    def __init__(self):
        # Setting up window
        
        tk.Tk.__init__(self)
        self.resizable(False,False)
        self.title("WattWheels")
        self.geometry("900x700")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.user_id = None
        self.user = None
        self.closing_window_open = False
        # Creating the database object
        Database.open()
        
        # Defining the default frame in which all windows will be updated
        self.container = tk.Frame(self, width=900, height=600)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW",self.on_closing)

        self.frames = {}

        # Storing all the pages in a dictionary
        for page in (Login, Signup, Client, Renting, Manager, Operator):
            page_name = page.__name__
            frame = page
            self.frames[page_name] = frame
            
        
        # Setting the default page to Login
        self.show_frame("Login")
    
    def set_user(self,user):
        """set_user
        Function to set the user_id and user object to a database record matching
        the parameter id
        
        Args:
            user (int): id of user to store as authenticated
        """    
        self.user_id = user
        if user != None:
            self.user = Database.selectOne(f"Select * from Users where id={user}")
        else:
            self.user = None
        
    def get_user(self):
        """get_user

        Returns:
            user_id: id of authenticated user
        """
        return self.user_id
    

    def get_user_obj(self):
        """get_user_obj
        Function to return authenticated user id, or None if no user
        is logged in
        
        Returns:
            id: int, id of the authenticated user
        """        
        if self.user_id != None:
            return Database.selectOne(f"Select * from Users where id={self.user_id}")
        else:
            return None
        
    def show_frame(self, page_name):
        """show_frame
        Function to display frame give by the parameter "page_name"
        Args:
            page_name (string): key in "frames" dictionary, with value being
                                the frame object to display
        """
        frame = self.frames[page_name]
        frame = frame(self.container,self)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.tkraise()
        
        
    def on_closing(self):
        """on_closing
        Function to display an exit confirmation box upon clicking the "X" button
        on the top right corner of the window
        """
        msg_box = messagebox.askquestion('Exit Application', 'Are you sure you want to quit?',icon='warning')
        if msg_box == "yes":
            self.quit()
            self.destroy()

    def logout(self):
        """logout
        Function to log out authenticated user, redirecting to login page
        Sets user_id and user to None
        """
        self.set_user(None)
        self.show_frame("Login")
app = MainApp()
app.mainloop()

Database.close()