import tkinter as tk
from tkinter import messagebox
from database.database import Database
from datetime import datetime
#from PIL import Image,ImageTk

class Client(tk.Frame):
    def __init__(self, parent, controller):
        """
        Initializes the Client page.

        Parameters
        ----------
        parent : tk.Tk
            The parent window of the Client page.
        controller : tk.Tk
            The main controller of the application.

        Returns
        -------
        None
        """
        tk.Frame.__init__(self, parent)
        self.user_window_open=False
        
        self.locations = Database.select("SELECT * FROM Locations")
        self.vehicles = Database.select('SELECT * FROM Vehicles where damage=0 and battery > 30 and status="stationary"')
        
        self.vehicleDict = {"Vehicle #{} - {}".format(x[0],x[1]):x[0] for x in self.vehicles if x} 
        self.locationDict = {x[1]:x[0] for x in self.locations}
        
        self.controller=controller
        self.user = self.controller.get_user_obj()
        self.create_widgets()
        
    def create_widgets(self):
        """
        Creates the widgets for the Client page.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        #  TITLE
        h1 = tk.Label(self,font=("Arial", 32))
        h1["justify"] = "center"
        h1["text"] = "Rent a vehicle"
        h1.place(x=30,y=30,width=650,height=50) 
        
        
        # User profile button code
        self.img = tk.PhotoImage(file="images/user.png")
        self.img = self.img.zoom(25)
        self.img = self.img.subsample(100)
        
        
        self.user_button = tk.Button(self, image=self.img, command=self.user_details, borderwidth=0)
        self.user_button.place(x=800,y=0,width=100,height=100)
        self.user_label = tk.Label(self, text=f"Hi, {self.user[3]}", bg="#67b0f0", fg="white",font=("Arial", 12))  # Styling
        self.user_label.place(x=580,y=30,width=100,height=40)
        self.logout_button = tk.Button(self, text="Logout", command=self.controller.logout, borderwidth=0)
        self.logout_button["bg"] = "#F1684B"
        self.logout_button.place(x=690,y=30,width=100,height=40)

        # Location selector dropdown code
        self.label = tk.Label(self, text="Select a city and vehicle", bg="#67b0f0", fg="white",font=("Arial", 12))  # Styling
        self.label.place(x=50,y=100,width=425,height=40)
        self.location_var = tk.StringVar()
        self.location_var.set(self.locations[0][1])  # Default location selection
        
        #Location filter
        self.location_selectbox = tk.OptionMenu(self, self.location_var, *self.locationDict.keys(),command= lambda _ : self.select_location(self.location_var))
        
        self.location_selectbox.place(x=50,y=150,width=425,height=40)
        
        self.select_button = tk.Button(self, text="Rent ✓", command=self.rent, font=("Arial", 15),bg="#9fe3bc", fg="white")  # Styling
        self.select_button.place(x=50,y=650,width=800,height=30)

        # Code for viewing and selecting vehicles
        self.vehicles_var = tk.StringVar(value=self.filter_vehicle_names_by_location(self.locations[0][0]))
        self.listbox = tk.Listbox(self, listvariable=self.vehicles_var, height=25, width=45, selectmode=tk.SINGLE,font=("Arial", 18),exportselection=False)
        self.listbox.place(x=50,y=190,width=400,height=425)
        self.listbox.bind("<<ListboxSelect>>", lambda _: self.display_selection())
        
        # VEHICLE DATA
        self.label = tk.Label(self, text="Vehicle data", bg="#67b0f0", fg="white",font=("Arial", 15))
        self.label.place(x=450,y=100,width=400,height=40)
        
        self.colorLabel = tk.Label(self,text="Color",font=("Arial",18),borderwidth=2, relief="groove")
        self.color_var = tk.StringVar()
        self.color = tk.Label(self,textvariable=self.color_var,font=("Arial",15),borderwidth=2, relief="groove")
        
        self.feeLabel = tk.Label(self,text="Fee(per second)",font=("Arial",18),borderwidth=2, relief="groove")
        self.fee_var = tk.StringVar()
        self.fee = tk.Label(self,textvariable=self.fee_var,font=("Arial",15),borderwidth=2, relief="groove")
        
        self.batteryLabel = tk.Label(self,text="Battery",font=("Arial",18),borderwidth=2, relief="groove")
        self.battery_var = tk.StringVar()
        self.battery = tk.Label(self,textvariable=self.battery_var,font=("Arial",15),borderwidth=2, relief="groove")
        
        self.damageLabel = tk.Label(self,text="Damage",font=("Arial",18),borderwidth=2, relief="groove")
        self.damage_var = tk.StringVar()
        self.damage = tk.Label(self,textvariable=self.damage_var,font=("Arial",15),borderwidth=2, relief="groove")
        

    def display_selection(self):
        """
        This function selects the vehicle from the listbox and displays the details of the vehicle.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        if self.location_var.get() and self.listbox.curselection():
            selected_vehicle = self.listbox.get(self.listbox.curselection())
            color,fee,battery,damage = Database.selectOne("Select color,fee,battery,damage from Vehicles where id={}".format(self.vehicleDict[selected_vehicle]))
            # Place detail widgets
            
            self.color_var.set(color)
            self.fee_var.set(fee)
            self.battery_var.set(battery)
            self.damage_var.set(damage)
            
            self.colorLabel.place(x=460,y = 190,width=200,height=100)
            self.color.place(x=660,y = 190,width= 200,height=100)
            self.feeLabel.place(x=460,y = 290,width=200,height=100)
            self.fee.place(x=660,y = 290,width= 200,height=100)
            self.batteryLabel.place(x=460,y = 390,width=200,height=100)
            self.battery.place(x=660,y = 390,width= 200,height=100)
            self.damageLabel.place(x=460,y = 490,width=200,height=100)
            self.damage.place(x=660,y = 490,width= 200,height=100)
            
        else:
            messagebox.showinfo("Error","Please select both Location & Vehicle")

    def user_details(self):
        """
        This function displays the user details in the popup window.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        if not self.user_window_open:
            def quit_application(userwindow):
                self.user_window_open=False
                userwindow.destroy()
                
            def add_to_balance(amount):
                try:
                    try:
                        amount = float(amount)
                    except ValueError:
                        raise ValueError("Amount must be a valid number")
                    if amount<0:
                        raise Exception("Amount must be a positive value")
                    amount = float(amount)
                    bal = round(amount + self.user[5],2)
                    Database.cud(f"UPDATE Users SET balance={bal} where id={self.user[0]}")
                    self.controller.set_user(self.user[0])
                    self.user = self.controller.get_user_obj()
                    bal_var.set(self.user[5])
                except Exception as e:
                    messagebox.showerror("Adding to balance failed", str(e))    
            
            self.user_window_open=True
            userwindow = tk.Toplevel(self)
            userwindow.title("User Details")
        
            x_pos = self.winfo_x() + 950  
            y_pos = self.winfo_y() + 120
        
            userwindow.geometry(f"300x150+{x_pos}+{y_pos}")
            userwindow.title("User Details")
            userwindow.resizable(False, False)
            userwindow.focus_force()
        
            name = tk.Label(userwindow,text="Username",font=("Arial",14))
            name.place(x=10,y=10,width=130,height=40)
            name_value = tk.Label(userwindow,text=self.user[3],font=("Arial",12))
            name_value.place(x=150,y=10,width=130,height=40)
        
            bal_var = tk.StringVar(value=self.user[5])
            balance = tk.Label(userwindow,text="Balance",font=("Arial",14))
            balance.place(x=10,y=50,width=130,height=40)
            balance_value = tk.Label(userwindow,textvariable=bal_var,font=("Arial",12))
            balance_value.place(x=150,y=50,width=130,height=40)
            
            to_add = tk.Entry(userwindow,font=("Arial",12))
            to_add.place(x=10,y=90,width=130,height=50)
            to_add_label = tk.Button(userwindow,text="Top up(£)",font=("Arial",12),bg="#67b0f0",fg="white",command=lambda: add_to_balance(to_add.get()))
            to_add_label.place(x=150,y=90,width=130,height=50)
            
            # Close this popup window when the focus is lost
            userwindow.bind("<FocusOut>", lambda _: quit_application(userwindow))

            userwindow.protocol("WM_DELETE_WINDOW", lambda: quit_application(userwindow))

    def select_location(self,var):
        """
        This function selects the location from the dropdown and displays the vehicles available in that location.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        location_id = self.locationDict[var.get()]
        
        vehicles = self.filter_vehicle_names_by_location(location_id)
        self.vehicles_var.set(vehicles)
        

    def filter_vehicle_names_by_location(self,location_id):
        return ["Vehicle #{} - {}".format(x[0],x[1]) for x in self.vehicles if x[4] == location_id]
    
    def filter_vehicles_by_location(self,location_id):
        return [x for x in self.vehicles if x[4] == location_id]


    def rent(self):
        """
        This function resnts the vehicle and inserts the rent data into the database.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        if self.location_var.get() and self.listbox.curselection():
            vehicle_id = self.vehicleDict[self.listbox.get(self.listbox.curselection())]
            user_id = self.user[0]
            location_id = self.locationDict[self.location_var.get()]
            damage = self.damage_var.get()
            
            now = datetime.now()

            # dd/mm/YY H:M:S
            time_string = now.strftime("%H:%M:%S")
            date_string = now.strftime("%d/%m/%Y")
            
            for v in self.vehicles:
                if v[0] ==  vehicle_id and self.user[-1] < v[3]:
                    messagebox.showerror("Insufficient balance","Please top up before renting this vehicle")
                    return
            
            try:
                Database.cud(f'INSERT INTO Rents(user_id, vehicle_id, pickup_date, pickup_time, dropoff_time, pickup_location, dropoff_location ,in_progress, damage, price) VALUES({user_id},{vehicle_id},"{date_string}","{time_string}",NULL,{location_id},NULL,1,{damage},0)')
                self.controller.show_frame("Renting")
            except Exception as e:
                messagebox.showerror("Renting error",str(e))
            
        else:
            messagebox.showinfo("Error","Please select vehicle to rent")