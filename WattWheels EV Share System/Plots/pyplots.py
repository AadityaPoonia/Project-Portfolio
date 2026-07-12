from database.database import Database
import pandas as pd

class Pyplots:
    def battery_status(figure):
        df = Database.dfTest("SELECT * FROM Vehicles")
        df = pd.DataFrame(df, columns=['type', 'battery'])
        ax = figure.add_subplot(111)
        df.plot(kind='bar',x='type',y='battery',ax=ax, color='green')
        ax.set_title("Battery Levels of Vehicles")
        ax.set_xlabel("Vehicle Type", fontsize=8)
        ax.set_ylabel("Battery Level", fontsize=8)
        return figure
    
    def vehicle_distribution(figure):
        df = Database.dfTest("SELECT l.name as locations, v.type, COUNT(v.type) AS vehicle_count FROM Locations AS l LEFT JOIN Vehicles AS v ON l.id = v.location_id GROUP BY l.name, v.type")
        df = df[df['type'] != 'None']
        pivot_df = df.pivot_table(index='locations', columns='type', values='vehicle_count', fill_value=0)
        ax = figure.add_subplot(111)
        ax = pivot_df.plot(kind='bar', stacked=False, ax=ax)
        ax.set_title("Vehicle distribution")
        ax.set_xlabel("Locations", fontsize=8)
        ax.set_ylabel("Vehicle Count", fontsize=8)
        return figure
    
    def vehicle_types(figure):
        df = Database.dfTest("SELECT type, COUNT(*) as count FROM Vehicles GROUP BY upper(type)")
        ax = figure.add_subplot(111)
        df.plot(kind='pie', y='count', labels=df['type'], ax=ax, legend=False, autopct='%1d%%')
        ax.set_title("Vehicle Types")
        ax.set_ylabel("")
        return figure
    
    def revenue_by_user(figure):
        df = Database.dfTest("SELECT users.name as uname, SUM(rents.price) AS total_paid from rents INNER JOIN users ON users.id = rents.user_id WHERE in_progress = 0 GROUP BY users.name ORDER BY total_paid DESC")
        if(len(df) == 0):
            return None
        ax = figure.add_subplot(111)
        df.plot(kind='bar', x='uname', y='total_paid', ax=ax, color='green')
        ax.set_title("Revenue by User")
        ax.set_xlabel("User", fontsize=8)
        ax.set_ylabel("Revenue", fontsize=8)
        return figure
    
    def revenue_generated_per_day(figure):
        df = Database.dfTest("SELECT pickup_date, SUM(price) AS day_total FROM Rents WHERE in_progress = 0 GROUP BY pickup_date")
        if(len(df) == 0):
            return None
        df.set_index('pickup_date', inplace=True)
        ax = figure.add_subplot(111)
        df.plot(kind='line', ax=ax, color='green', marker='o')
        ax.set_title("Revenue Generated Per Day")
        ax.set_xlabel("Date", fontsize=8)
        ax.set_ylabel("Revenue", fontsize=8)
        return figure
    
    def avg_time_of_vehicles_used(figure):
        df = Database.dfTest("SELECT v.type as vehicle_type, pickup_time, dropoff_time from rents INNER JOIN vehicles v ON vehicle_id = v.id WHERE in_progress = 0")
        if(len(df) == 0):
            return None
        df['pickup_time'] = pd.to_datetime(df['pickup_time'], format='%H:%M:%S')
        df['dropoff_time'] = pd.to_datetime(df['dropoff_time'], format='%H:%M:%S')

        df['time_diff'] = (df['dropoff_time'] - df['pickup_time']).dt.total_seconds()
        time_diff = df.groupby('vehicle_type')['time_diff'].mean()
        time_diff = pd.DataFrame(time_diff)
        ax = figure.add_subplot(111)
        time_diff.plot(kind='line', ax=ax, color='green', marker='o')
        ax.set_title("Average Time of Vehicles Used")
        ax.set_xlabel("Vehicle Type", fontsize=8)
        ax.set_ylabel("Average Time (seconds)", fontsize=8)

        return figure
        