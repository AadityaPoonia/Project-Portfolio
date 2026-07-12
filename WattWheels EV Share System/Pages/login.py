import tkinter as tk
from tkinter import messagebox
import sqlite3
import argon2
from database.database import Database
# from signup import Signup

class Login(tk.Frame):
    def __init__(self, parent, controller):
        """
        Initializes the Login page.

        Parameters
        ----------
        parent : tk.Tk
            The parent window of the Login page.
        controller : tk.Tk
            The main controller of the application.
        """
        tk.Frame.__init__(self, parent)
        
        self.controller=controller
        self.create_widgets()
    
    def create_widgets(self):
        """
        Creates the widgets for the Login page.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """

        #email section

        ev_desc_img = tk.PhotoImage(file="images/ev_desc_final.png")
        self.ev_desc = tk.Label(self, image=ev_desc_img, compound="center")
        self.ev_desc.image = ev_desc_img
        self.ev_desc.place(x=40,y=40,width=380,height=610)

        self.emailLabel=tk.Label(self,text="Email:")
        self.emailLabel["font"] = ('Arial', '18')
        self.emailLabel.place(x=460,y=180,width=96,height=46)


        self.emailBox = tk.Entry(self,width=30)
        self.emailBox["font"] = ('Arial', '23')
        self.emailBox['justify'] = 'left'
        self.emailBox.place(x=480,y=230,width=355,height=50)

        #password section

        self.passwordLabel=tk.Label(self,text="Password:")
        self.passwordLabel["font"] = ('Arial', '18')
        self.passwordLabel.place(x=480,y=310,width=116,height=38)
        
        self.passwordBox = tk.Entry(self,width=30, show="*")
        self.passwordBox["font"] = ('Arial', '23')
        self.passwordBox['justify'] = 'left'
        self.passwordBox.place(x=480,y=350,width=355,height=50)

        #Buttons
        
        self.loginButton = tk.Button(self,text="Log in", command=self.authenticate_user, bd=5,bg="#9fe3bc")
        self.loginButton["font"] = ('Arial', '18')
        self.loginButton.place(x=600,y=460,width=130,height=40)
        
        self.signupButton = tk.Label(self, text="Sign Up", bd=5, fg="#0000EE")
        self.signupButton.bind("<Button-1>", lambda e: self.controller.show_frame("Signup"))
        self.signupButton["font"] = ('Arial', '16', 'underline')
        self.signupButton.place(x=600,y=530,width=130,height=40)
        
    def authenticate_user(self):
        """
        Authenticates the user's login credentials.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        user_email = self.emailBox.get()
        user_password = self.passwordBox.get()
        try:
            data = Database.select('SELECT email, password,role,id FROM Users WHERE email = "{}"'.format(str(user_email)))
            
            
            if data is not None and len(data) > 0:
                row = data[0]

                key = argon2.PasswordHasher()
                
                db_user, db_pwd, db_userType,user_id = row
                rented=Database.selectOne('SELECT count(in_progress) FROM Rents WHERE Rents.user_id ="{}" and in_progress = 1'.format((user_id)))[0]
                self.controller.set_user(user_id)
                try:
                    if key.verify(db_pwd, user_password):
                        if rented > 0:
                            if db_userType.lower()=="user":
                                self.controller.show_frame("Renting")
                        else:
                            if db_userType.lower()=="user":
                                self.controller.show_frame("Client")
                            
                            elif db_userType.lower()=="operator":
                                self.controller.show_frame("Operator")
                            elif db_userType.lower()=="manager":
                                self.controller.show_frame("Manager")
                except argon2.exceptions.VerificationError:
                    messagebox.showerror("Login Failed", "Incorrect credentials")
            else:
                messagebox.showerror("Login Failed", "User not found")
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
      
