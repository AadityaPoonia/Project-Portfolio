import tkinter as tk
from database.database import Database
from datetime import datetime

class Renting(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller=controller
        self.db_userid = self.controller.get_user()
        self.user_window_open=False
        self.locations = Database.select("SELECT * FROM Locations")
        self.locationDict = {x[1]:x[0] for x in self.locations}
        self.create_widgets()

    def create_widgets(self):
        """
        This function creates all the widgets required for the renting page.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        
        
        # Fetching data from database
        if self.db_userid:
            self.vid_uid=Database.select('SELECT vehicle_id, user_id FROM Rents WHERE user_id="{}" AND in_progress=1'.format(self.db_userid)) 
        else:
            self.vid_uid=None       
        if self.vid_uid:
            data=Database.select("SELECT rent_id, Users.name AS Name,balance,rents.pickup_date,rents.pickup_time,Locations.name as pickup_location, Vehicles.type AS Vehicle, Vehicles.fee as fee, battery FROM Vehicles,Rents,Users,Locations WHERE Rents.vehicle_id=Vehicles.id AND Rents.in_progress=1 AND Rents.pickup_location = Locations.id AND Vehicles.id={} AND Users.id={}".format(self.vid_uid[0][0],self.vid_uid[0][1]))[0]
        else:
            data=None 
            
        if data is not None:

            # Create label and value pairs for each column
            labels = ["rent_id", "Name", "balance", "pickup date", "pickup time", "pickup location", "Vehicle", "fee", "battery"]
            self.value_dict = dict((labels[x], y) for x, y in enumerate(data))

            retingDetailsTitleLabel=tk.Label(self)
            retingDetailsTitleLabel["font"] = ('Arial', '28')
            retingDetailsTitleLabel["fg"] = "#333333"
            retingDetailsTitleLabel["justify"] = "center"
            retingDetailsTitleLabel["text"] = "Renting Details"
            retingDetailsTitleLabel.place(x=250,y=10,width=419,height=40)

            vehicleTypeTitleLabel=tk.Label(self)
            vehicleTypeTitleLabel["font"] = ('Arial', '19')
            vehicleTypeTitleLabel["fg"] = "#333333"
            vehicleTypeTitleLabel["justify"] = "center"
            vehicleTypeTitleLabel["text"] = "Vehicle: "
            vehicleTypeTitleLabel.place(x=310,y=110,width=100,height=30)

            label_vehicle_type=tk.Label(self)
            label_vehicle_type["font"] = ('Arial', '19')
            label_vehicle_type["fg"] = "#333333"
            label_vehicle_type["justify"] = "center"
            label_vehicle_type["text"] = self.value_dict['Vehicle']
            label_vehicle_type.place(x=500,y=110,width=180,height=30)

            dateTimeTitleLabel=tk.Label(self)
            dateTimeTitleLabel["font"] = ('Arial', '19')
            dateTimeTitleLabel["fg"] = "#333333"
            dateTimeTitleLabel["justify"] = "center"
            dateTimeTitleLabel["text"] = "Date and time rented: "
            dateTimeTitleLabel.place(x=170,y=170,width=250,height=30)

            label_date_time=tk.Label(self)
            label_date_time["font"] = ('Arial', '19')
            label_date_time["fg"] = "#333333"
            label_date_time["justify"] = "center"
            label_date_time["text"] = self.value_dict['pickup date'] + "::" +self.value_dict['pickup time']
            label_date_time.place(x=500,y=170,width=250,height=25)

            cpsTitleLabel=tk.Label(self)
            cpsTitleLabel["font"] = ('Arial', '19')
            cpsTitleLabel["fg"] = "#333333"
            cpsTitleLabel["justify"] = "center"
            cpsTitleLabel["text"] = "Cost per second: "
            cpsTitleLabel.place(x=200,y=230,width=216,height=30)

            label_cost_per_sec=tk.Label(self)
            label_cost_per_sec["font"] = ('Arial', '19')
            label_cost_per_sec["fg"] = "#333333"
            label_cost_per_sec["justify"] = "center"
            label_cost_per_sec["text"] = str(self.value_dict['fee']) + " £/Second"
            label_cost_per_sec.place(x=500,y=230,width=200,height=25)

            curr_status=tk.Label(self)
            curr_status["font"] = ('Arial', '19')
            curr_status["fg"] = "#333333"
            curr_status["justify"] = "center"
            curr_status["text"] = "Current status: "
            curr_status.place(x=200,y=280,width=216,height=30)

            curr_status_rented=tk.Label(self)
            curr_status_rented["font"] = ('Arial', '19')
            curr_status_rented["fg"] = "#51D055"
            curr_status_rented["justify"] = "center"
            curr_status_rented["text"] = "Ongoing rent"
            curr_status_rented.place(x=500,y=280,width=200,height=40)

            endRentalBtn=tk.Button(self)
            endRentalBtn["bg"] = "#F1684B"
            endRentalBtn["font"] = ('Arial', '10')
            endRentalBtn["fg"] = "#FFFFFF"
            endRentalBtn["justify"] = "center"
            endRentalBtn["text"] = "END RENTAL"
            endRentalBtn.place(x=390,y=350,width=155,height=52)
            endRentalBtn["command"] = self.end_rental
        else:
            pass

    def end_rental(self):
        """
        This function creates the end rental popup window when the user wants to end the current rental.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        if not self.user_window_open:
            time_diff = datetime.now() - datetime.strptime(self.value_dict['pickup time'], "%H:%M:%S")
            total_cost = time_diff.seconds * self.value_dict['fee']

            damaged = tk.IntVar()

            self.user_window_open=True
            userwindow = tk.Toplevel(self)
            userwindow.title("Confirm End Rental")

            window_height = 362
            window_width = 554

            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()

            x_cordinate = int((screen_width/2) - (window_width/2))
            y_cordinate = int((screen_height/2) - (window_height/2))

            userwindow.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))
            
            userwindow.resizable(False, False)
            userwindow.focus_force()
            userwindow.bind("<FocusOut>", lambda _: quit_application(userwindow))
            userwindow.protocol("WM_DELETE_WINDOW", lambda: quit_application(userwindow))

            totalCostTitleLabel=tk.Label(userwindow)
            totalCostTitleLabel["font"] = ("Arial", "28")
            totalCostTitleLabel["fg"] = "#333333"
            totalCostTitleLabel["justify"] = "center"
            totalCostTitleLabel["text"] = "Total Cost: "
            totalCostTitleLabel.place(x=90,y=30,width=180,height=47)

            totalCostLabel=tk.Label(userwindow)
            totalCostLabel["font"] = ("Arial", "28")
            totalCostLabel["fg"] = "#333333"
            totalCostLabel["justify"] = "center"
            totalCostLabel["text"] = str(total_cost) + " £"
            totalCostLabel.place(x=290,y=30,width=224,height=47)

            timeRentedTitleLabel=tk.Label(userwindow)
            timeRentedTitleLabel["font"] = ("Arial", "28")
            timeRentedTitleLabel["fg"] = "#333333"
            timeRentedTitleLabel["justify"] = "center"
            timeRentedTitleLabel["text"] = "Time Rented: "
            timeRentedTitleLabel.place(x=20,y=90,width=266,height=51)

            timeDiffLabel=tk.Label(userwindow)
            timeDiffLabel["font"] = ("Arial", "28")
            timeDiffLabel["fg"] = "#333333"
            timeDiffLabel["justify"] = "center"
            timeDiffLabel["text"] = str(time_diff.seconds) + " seconds"
            timeDiffLabel.place(x=300,y=90,width=214,height=50)

            dropLocationTitleLabel=tk.Label(userwindow)
            dropLocationTitleLabel["font"] = ("Arial", "28")
            dropLocationTitleLabel["fg"] = "#333333"
            dropLocationTitleLabel["justify"] = "center"
            dropLocationTitleLabel["text"] = "Drop Location: "
            dropLocationTitleLabel.place(x=0,y=150,width=290,height=54)

            # location dropdown code
            location_var = tk.StringVar()
            location_var.set(self.locations[0][1])
            self.location_selectbox = tk.OptionMenu(userwindow, location_var, *self.locationDict.keys())
            self.location_selectbox.place(x=320, y=170,height=24, width=174)

            reportDamagedChkBox=tk.Checkbutton(userwindow, variable=damaged)
            reportDamagedChkBox["font"] = ('Arial', '18')
            reportDamagedChkBox["fg"] = "#333333"
            reportDamagedChkBox["justify"] = "center"
            reportDamagedChkBox["text"] = "Report Damaged"
            reportDamagedChkBox.place(x=140,y=230,width=280,height=45)
            reportDamagedChkBox["offvalue"] = "0"
            reportDamagedChkBox["onvalue"] = "1"
            # reportDamagedChkBox["command"] = self.reportDamagedChkBox_command

            payAndEndBtn=tk.Button(userwindow)
            payAndEndBtn["bg"] = "#9fe3bc"
            payAndEndBtn["font"] = ('Arial', '18')
            payAndEndBtn["fg"] = "#000000"
            payAndEndBtn["justify"] = "center"
            payAndEndBtn["text"] = "Pay and End Rental"
            payAndEndBtn.place(x=110,y=290,width=322,height=45)
            payAndEndBtn["command"] = lambda: end_rental(userwindow)
            
        def quit_application(userwindow):
            self.user_window_open=False
            userwindow.destroy()

        def end_rental(userwindow):
            """
            This function ends the ongoing rental, updates the database and navigates back to the client landing page for a new rental.

            Parameters
            ----------
            userwindow : tk.Toplevel
                The window that is currently open.
            
            Returns
            -------
            None
            """
            # set status of rented to 0 in the rents table
            # update drop off time in the rents table
            # update fee in the rents table
            Database.cud("UPDATE Rents SET in_progress=0, dropoff_time='{}', dropoff_location={}, damage={}, price={} WHERE rent_id={}".format(datetime.now().strftime("%H:%M:%S"), self.locationDict[location_var.get()], damaged.get(), total_cost, self.value_dict['rent_id']))

            # update location, status, battery and damage in the vehicles table
            Database.cud("UPDATE Vehicles SET location_id={}, status='stationary', battery=battery-{}, damage={} WHERE id={}".format(self.locationDict[location_var.get()], round(time_diff.seconds * 0.25), damaged.get(), self.vid_uid[0][0]))

            # update balance in the users table
            Database.cud("UPDATE Users SET balance=balance-{} WHERE id={}".format(round(total_cost,2), self.vid_uid[0][1]))

            # go to the client page
            quit_application(userwindow)
            self.controller.show_frame("Client")
