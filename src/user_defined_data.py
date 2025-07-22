import pandas as pd

import pandas as pd

def read_user_data(file_path='user_data.csv'):
    try:
        # Read only the 19th row (index 18 since pandas uses 0-based indexing)
        df = pd.read_csv(file_path, skiprows=18, nrows=1, header=None)
        
        # Extract the numeric value from the first column
        user_choice = df.iloc[0, 0]
        
        # Convert to integer
        return int(user_choice)
    except FileNotFoundError:
        print(f"Error: {file_path} not found. Using default value.")
        return 16
    except ValueError:
        print("Error: Invalid choice value in CSV. Using default value.")
        return 16
    except Exception as e:
        print(f"Unexpected error: {str(e)}. Using default value.")
        return 16


