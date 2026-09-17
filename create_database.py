import pandas as pd
import sqlite3

# load dataset
data = pd.read_csv("A_Z_medicines_dataset_of_India.csv")

# select only important columns
data = data[[
"name",
"price(₹)",
"manufacturer_name",
"short_composition1"
]]

# create sqlite database
conn = sqlite3.connect("medinsta.db")

# create table
data.to_sql("medicines", conn, if_exists="replace", index=False)

conn.close()

print("Database created successfully")