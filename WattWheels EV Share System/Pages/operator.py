import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from database.database import Database

class Operator(tk.Frame):
     def __init__(self,parent,controller):
          tk.Frame.__init__(self, parent)
          self.controller=controller
          
          self.damaged_var=0
          self.battery_var=0
          
          #fetching data
          self.vehicles=Database.select('select * from Vehicles join Locations where Vehicles.location_id=Locations.id')
          for i in self.vehicles:
               self.damcheck=i[7]
               self.batcheck=i[5]
               if self.damcheck=='1' or self.damcheck==1:
                    self.damaged_var=self.damaged_var+1
               if int(self.batcheck)<30:
                    self.battery_var=self.battery_var+1
                  
          self.create_widgets()
    
     def create_widgets(self):
          """
          This function creates all the widgets in the operator page.

          Parameters
          ----------
          None

          Returns
          -------
          None
          """
          #log out button
          self.logout_button = tk.Button(self, text="Logout", command=self.controller.logout, borderwidth=0,bg="#F1684B")
          self.logout_button.place(x=800,y=0,width=100,height=30)
          
          #register vehicle button
          self.regbutton=tk.Button(self,text='Register Vehicle +',command=self.register_new_vehicle,bg="#67b0f0", fg="white",font=("Arial",15))
          self.regbutton.place(x=300,y=10,width=300,height=50)
          #move vehicle button
          self.movebutton=tk.Button(self,text='Move vehicles ⇅',command=self.move_vehicle,bg="#67b0f0", fg="white",font=("Arial",15))
          self.movebutton.place(x=300,y=70,width=300,height=50)


          #damaged vehicles section
          self.damagedbutton=tk.Button(self,text='Show damaged vehicles',command=self.fetch_damaged,bg="#67b0f0", fg="white")
          self.damagedbutton.place(x=50,y=30,width=200,height=30)

          #Battery section
          self.batterybutton=tk.Button(self,text='Show low battery vehicles',command=self.fetch_batterylow,bg="#67b0f0", fg="white")
          self.batterybutton.place(x=50,y=80,width=200,height=30)

          self.showallbutton=tk.Button(self,text="Show all vehicles",command=self.fetch_all,bg="#67b0f0", fg="white")
          self.showallbutton.place(x=50,y=130,width=200,height=30)

          self.sep=ttk.Separator(self,orient='horizontal').place(relx=0, rely=0.47, relwidth=1, relheight=4)

          #Charge,repair and show icons
          tk.Label(self,text="🔋",font=(20)).place(x=775,y=30,width=125,height=30)
          tk.Label(self,text="🛠",font=(20)).place(x=650,y=30,width=125,height=30)
          tk.Label(self,text="🗄",font=(20)).place(x=50,y=0,width=200,height=30)

          #Button for recharge
          self.rechargebutton=tk.Button(self,text='Recharge selected',bg="#9fe3bc",command=self.rechargesel)
          self.rechargebutton.place(x=775,y=80,width=125,height=30)

          self.rechargeallbutton=tk.Button(self,text='Recharge All',bg="#9fe3bc",command=self.rechargeall)
          self.rechargeallbutton.place(x=775,y=130,width=125,height=30)
          #Button for repair
          self.repairbutton=tk.Button(self,text='Repair selected',bg="#9fe3bc",command=self.repairsel)
          self.repairbutton.place(x=650,y=80,width=125,height=30)

          self.repairallbutton=tk.Button(self,text='Repair all',bg="#9fe3bc",command=self.repairall)
          self.repairallbutton.place(x=650,y=130,width=125,height=30)


          #label for treeview
          self.mystrvar=tk.StringVar()
          self.treeviewlabel=tk.Label(self,textvariable=self.mystrvar,font=("Arial",18))
          self.treeviewlabel.place(x=300,y=125,width=300,height=50)
       


          #treeview code

          self.treeview=ttk.Treeview(self,column=("c1", "c2", "c3","c4","c5"), show='headings', height=24,selectmode="browse")
          self.treeview.place(x=0,y=200)
          self.treeview.column("# 1", anchor=tk.CENTER,stretch=tk.NO,width=50)
          self.treeview.heading("# 1", text="ID")
          self.treeview.column("# 2", anchor=tk.CENTER,stretch=tk.NO,width=200)
          self.treeview.heading("# 2", text="Type")
          self.treeview.column("# 3", anchor=tk.CENTER,stretch=tk.NO,width=400)
          self.treeview.heading("# 3", text="Location")
          self.treeview.column("# 4", anchor=tk.CENTER,stretch=tk.NO,width=125)
          self.treeview.heading("# 4", text="Damage(0/1)")
          self.treeview.column("# 5", anchor=tk.CENTER,stretch=tk.NO,width=125)
          self.treeview.heading("# 5", text="Battery(%)")
          
          self.fetch_all()
          


     #
     def select_item(self):
          """
          This function fetches user selected item from treeview.

          Parameters
          ----------
          None

          Returns
          -------
          None
          """
          curItem = self.treeview.focus()
          dict=self.treeview.item(curItem)
          return dict['values']
     
     def rechargesel(self):
          """
          This function recharges the selected vehicle in the treeview.

          Parameters
          ----------
          None

          Returns
          -------
          None
          """
          selected=self.select_item()
          
          if not selected:
               messagebox.showerror("Charging error","Please select a vehicle to charge")
               return
          
          try:
               Database.cud(f"UPDATE Vehicles SET battery=100 where id={selected[0]}")
               # Re-fetch and reload data in table
               self.vehicles=Database.select('select * from Vehicles join Locations where Vehicles.location_id=Locations.id')
               self.fetch_all()
               messagebox.showinfo("Repair", "Vehicle charged successfully")
          except Exception as ex:
               messagebox.showerror("Database error", "Charging failed")

     def rechargeall(self):
          """
          This function recharges all vehicles in the treeview.

          Parameters
          ----------
          None

          Returns
          -------
          None
          """
          try:
               Database.cud("UPDATE Vehicles SET battery=100")
               # Re-fetch and reload data in table
               self.vehicles=Database.select('select * from Vehicles join Locations where Vehicles.location_id=Locations.id')
               self.fetch_all()
               messagebox.showinfo("Repair", "Vehicles charged successfully")
          except Exception as ex:
               messagebox.showerror("Database error", "Charging failed")
     
     def repairsel(self):
          """
          This function repairs the selected vehicle in the treeview.

          Parameters
          ----------
          None

          Returns
          -------
          None
          """
          selected=self.select_item()
          
          if not selected:
               messagebox.showerror("Repairing error","Please select a vehicle to repair")
               return
          
          try:
               Database.cud(f"UPDATE Vehicles SET damage=0 where id={selected[0]}")
               # Re-fetch and reload data in table
               self.vehicles=Database.select('select * from Vehicles join Locations where Vehicles.location_id=Locations.id')
               self.fetch_all()
               messagebox.showinfo("Repair", "Vehicle repaired successfully")
          except Exception as ex:
               messagebox.showerror("Database error", "Repairing failed")

     def repairall(self):
          """
          This function repairs all vehicles in the treeview.

          Parameters
          ----------
          None

          Returns
          -------
          None
          """
          try:
               Database.cud("UPDATE Vehicles SET damage=0")
               # Re-fetch and reload data in table
               self.vehicles=Database.select('select * from Vehicles join Locations where Vehicles.location_id=Locations.id')
               self.fetch_all()
               messagebox.showinfo("Repair", "Vehicles repaired successfully")
          except Exception as ex:
               messagebox.showerror("Database error", "Repairing failed")
     
     def move_vehicle(self):
          """
          This function moves the selected vehicle to a different location in the treeview.

          Parameters
          ----------
          None

          Returns
          -------
          None
          """
          locations = Database.select("SELECT * FROM Locations")
          locationDict = {x[1]:x[0] for x in locations}
          
          
          vehicle = self.select_item()
          location = locations[0][1]
          
          if type(vehicle) == list and type(list[0]) != list:
               location = vehicle[2].split(",")[0]
               vehicle = vehicle[0]
          else:
               messagebox.showerror("Moving vehicle failed", "Please select one vehicle from the list below")
               return
               
          self.move_win = tk.Tk()
          self.move_win.geometry("400x400")
          
          loc_label=tk.Label(self.move_win,text=f'New Location for vehicle#{vehicle}:')       
          loc_label["font"] = ("Arial", "20")
          loc_label["fg"] = "#333333"
          loc_label["justify"] = "center"
          loc_label.place(x=10,y=100,width=380,height=50)
          
          location_var = tk.StringVar(self.move_win)
          location_var.set(location)
          location = tk.OptionMenu(self.move_win, location_var, *locationDict.keys())
          location.place(x=50,y=200,width=300,height=50)
     
          tk.Button(self.move_win,text="Submit",bg="#9fe3bc",command=lambda: self.change_vehicle_location(locationDict[location_var.get()],vehicle)).place(x=100,y=300,width=200,height=50)
          self.move_win.focus_force()
          self.move_win.bind("<FocusOut>", lambda _: self.move_win.destroy())
          self.move_win.mainloop()

     def change_vehicle_location(self,loc,veh):
          """
          This function changes the location of the vehicle in the database.

          Parameters
          ----------
          loc : int
               The new location id of the vehicle
          veh : int
               The vehicle id of the vehicle to be moved

          Returns
          -------
          None
          """
          try:
               Database.cud(f"Update Vehicles set location_id = {loc} where id={veh}")
               # Re-fetch vehicle data
               self.vehicles=Database.select('select * from Vehicles join Locations where Vehicles.location_id=Locations.id')
               self.fetch_all()
               # Destroy temp window
               self.move_win.destroy()
          except Exception as ex:
               messagebox.showerror("Database error", "Moving vehicle failed")

     def fetch_damaged(self):
          """
          This function fetches all damaged vehicles in the treeview.

          Parameters
          ----------
          None

          Returns
          -------
          None
          """
          for i in self.treeview.get_children():
               self.treeview.delete(i)
          self.mystrvar.set("Damaged vehicles")
          self.mynum=1
          for i in self.vehicles:
               if int(i[7])==1:
                    self.locvar=str(i[-3]) + ','+str(i[-2])+','+str(i[-1])
                    self.treeview.insert('', 'end',text= self.mynum,values=(i[0],i[1],self.locvar,i[7],i[5]))
                    self.mynum=self.mynum+1
          
     def fetch_batterylow(self):
          """
          This function fetches all low battery vehicles in the treeview.

          Parameters
          ----------
          None

          Returns
          -------
          None
          """
          for i in self.treeview.get_children():
               self.treeview.delete(i)
          self.mystrvar.set("Low battery vehicles")
          self.mynum=1
          for i in self.vehicles:
               if int(i[5])<30:

                    self.locvar=str(i[-3]) + ','+str(i[-2])+','+str(i[-1])
                    self.treeview.insert('', 'end',text=self.mynum,values=(i[0],i[1],self.locvar,i[7],i[5]))
                    self.mynum=self.mynum+1
                    
     
     def fetch_all(self):
          """
          This function fetches all vehicles in the treeview.

          Parameters
          ----------
          None

          Returns
          -------
          None
          """
          for i in self.treeview.get_children():
               self.treeview.delete(i)
          self.mystrvar.set("All vehicles")
          self.mynum=1
          for i in self.vehicles:
               self.locvar=str(i[-3]) + ','+str(i[-2])+','+str(i[-1])
               self.treeview.insert('', 'end',text= self.mynum,values=(i[0],i[1],self.locvar,i[7],i[5]))
               self.mynum=self.mynum+1
          

     def submit_to_db(self,type,color,fee,location):
          """
          This function submits the new vehicle to the database.

          Parameters
          ----------
          type : string
               The type of the vehicle
          color : string
               The color of the vehicle
          fee : int
               The fee of the vehicle
          location : int
               The location id of the vehicle

          Returns
          -------
          None
          """
          
          
          try:
               if not fee.isnumeric() or float(fee) <= 0:
                    raise Exception("Please enter valid numeric value for fee(>0)")
               
               if not (len(type) > 0 and len(color) > 0 and location):
                    raise Exception("Please enter all the data to register a new vehicle")

               Database.cud('INSERT INTO Vehicles(type, color, fee, location_id, battery, status, damage)  VALUES("{}","{}",{},{},100,"stationary",0)'.format(type,color,fee,location))
               self.add_win.destroy()
               
               # Re-query the vehicle data after inserting
               self.vehicles=Database.select('select * from Vehicles join Locations where Vehicles.location_id=Locations.id')
               self.fetch_all()
          except Exception as ex:
               messagebox.showerror("Creating vehicle failed", ex)
               self.add_win.focus_force()
                    
          
     
     def register_new_vehicle(self):
          """
          This function creates a new window to register a new vehicle.

          Parameters
          ----------
          None

          Returns
          -------
          None
          """
          # Location data
          locations = Database.select("SELECT * FROM Locations")
          locationDict = {x[1]:x[0] for x in locations}
          
          self.add_win=tk.Tk()
          self.add_win.geometry('400x400')
          
          type_label=tk.Label(self.add_win,text='Type:')
          type_label["font"] = ("Arial", "20")
          type_label["fg"] = "#333333"
          type_label["justify"] = "center"
          type_label.place(x=0,y=30,width=150,height=50)
          
          color_label=tk.Label(self.add_win,text='Color:')
          color_label["font"] = ("Arial", "20")
          color_label["fg"] = "#333333"
          color_label["justify"] = "center"
          color_label.place(x=0,y=100,width=150,height=50)
            
          fee_label=tk.Label(self.add_win,text='Fee:')
          fee_label["font"] = ("Arial", "20")
          fee_label["fg"] = "#333333"
          fee_label["justify"] = "center"
          fee_label.place(x=0,y=170,width=150,height=50)
          
          loc_label=tk.Label(self.add_win,text='Location:')       
          loc_label["font"] = ("Arial", "20")
          loc_label["fg"] = "#333333"
          loc_label["justify"] = "center"
          loc_label.place(x=0,y=240,width=150,height=50)


          #entry widgets
          type =tk.Entry(self.add_win)
          type.place(x=200,y=30,width=150,height=50)
          type.focus_force()
          color=tk.Entry(self.add_win)
          color.place(x=200,y=100,width=150,height=50)
          fee=tk.Entry(self.add_win)
          fee.place(x=200,y=170,width=150,height=50)
          location_var = tk.StringVar(self.add_win)
          location_var.set(locations[0][1])
          location = tk.OptionMenu(self.add_win, location_var, *locationDict.keys())
          location.place(x=200,y=240,width=180,height=50)
          tk.Button(self.add_win,text="Submit",bg="#9fe3bc",command=lambda: self.submit_to_db(type.get(),color.get(),fee.get(),locationDict[location_var.get()])).place(x=100,y=350,width=200,height=50)
          self.add_win.bind("<FocusOut>", lambda _: self.add_win.destroy())
          self.add_win.mainloop()
     