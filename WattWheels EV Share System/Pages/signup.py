import tkinter as tk
from tkinter import messagebox
import argon2
from database.database import Database

class Signup(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller=controller
        self.create_widgets()
    
    def create_widgets(self):
        ev_desc_img = tk.PhotoImage(file="images/ev_desc_final.png")
        self.ev_desc = tk.Label(self, image=ev_desc_img, compound="center")
        self.ev_desc.image = ev_desc_img
        self.ev_desc.place(x=40,y=40,width=380,height=610)
        #name

        self.nameLabel=tk.Label(self,text="Name:")
        self.nameLabel["font"] = ('Arial', '18')
        self.nameLabel.place(x=460,y=70,width=96,height=46)


        self.nameBox = tk.Entry(self,width=30)
        self.nameBox["font"] = ('Arial', '23')
        self.nameBox["justify"] = "left"
        self.nameBox.place(x=460,y=130,width=400,height=50)

        #email
        self.emailLabel=tk.Label(self,text="Email:")
        self.emailLabel["font"] = ('Arial', '18')
        self.emailLabel.place(x=460,y=180,width=96,height=46)


        self.emailBox = tk.Entry(self,width=30)
        self.emailBox["font"] = ('Arial', '23')
        self.emailBox['justify'] = 'left'
        self.emailBox.place(x=460,y=230,width=400,height=50)

        #password
        self.passwordLabel=tk.Label(self,text="Password:")
        self.passwordLabel["font"] = ('Arial', '18')
        self.passwordLabel.place(x=460,y=280,width=126,height=38)
        
        self.passwordBox = tk.Entry(self,width=30, show="*")
        self.passwordBox["font"] = ('Arial', '23')
        self.passwordBox['justify'] = 'left'
        self.passwordBox.place(x=460,y=330,width=400,height=50)

        
        #phone num
        self.phoneLabel=tk.Label(self,text="Phone:")
        self.phoneLabel["font"] = ('Arial', '18')
        self.phoneLabel.place(x=460,y=380,width=96,height=38)

        self.phoneBox = tk.Entry(self,width=30)
        self.phoneBox["font"] = ('Arial', '23')
        self.phoneBox['justify'] = 'left'
        self.phoneBox.place(x=460,y=430,width=400,height=50)


        #Button
        self.signupButton = tk.Button(self,text="Sign up", command=self.signup_user, bd=5,bg="#9fe3bc")
        self.signupButton["font"] = ('Arial', '18')
        self.signupButton.place(x=600,y=550,width=130,height=40)
        
        self.loginButton = tk.Label(self, text="Already have an account? Log in!", bd=5, fg="#0000EE")
        self.loginButton.bind("<Button-1>", lambda e: self.controller.show_frame("Login"))
        self.loginButton["font"] = ('Arial', '16', 'underline')
        self.loginButton.place(x=460,y=600,width=400,height=40)

    def signup_user(self):
        
        user_name=self.nameBox.get()
        user_email=self.emailBox.get()
        user_password=self.passwordBox.get()
        user_phone=self.phoneBox.get()
        
        lock=argon2.PasswordHasher()
        hash_password=lock.hash(user_password)
        try:
            #save to db code after field checks
            if not ("@" in user_email and "." in user_email and len(user_email.split("@") == 2) and len(user_email.split('@')[0]) > 0  and len(user_email.split('@')[1]) > 0 ):
                raise Exception("Please enter a valid email(example@mail.com)")
            
            if not (len(user_email) > 0 
                and len(user_password) > 0
                and len(user_name) > 0
                and len(user_phone) > 0):
                raise Exception("Please provide all the attributes")
            
            Database.cud('INSERT INTO Users(email, password, name, role, balance) VALUES("{}","{}","{}","{}","{}")'.format(user_email,hash_password,user_name,"user",0))
            
            user_id = Database.selectOne(f'SELECT id from Users WHERE email="{user_email}"')[0]
            # show dialog box saying "Login to continue"
            self.controller.set_user(user_id)
            self.controller.show_frame("Client")
        except Exception as ex:
            messagebox.showerror("Database error", ex)
        