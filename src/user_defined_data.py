import pandas as pd


# def read_user_data(file_path='user_data.csv'):
#     try:
#         # Read only the 19th row (index 18 since pandas uses 0-based indexing)
#         df = pd.read_csv(file_path, skiprows=18, nrows=1, header=None)
        
#         # Extract the numeric value from the first column
#         user_choice = df.iloc[0, 0]
        
#         # Convert to integer
#         return int(user_choice)
#     except FileNotFoundError:
#         print(f"Error: {file_path} not found. Using default value.")
#         return 16
#     except ValueError:
#         print("Error: Invalid choice value in CSV. Using default value.")
#         return 16
#     except Exception as e:
#         print(f"Unexpected error: {str(e)}. Using default value.")
#         return 16


import pandas as pd

def read_user_data(file_path='user_data.csv'):
    """
    Reads user_choice and write_file_info flag from specific rows in the CSV.
    
    Assumes:
    - Line 19 (index 18) contains user choice as an integer.
    - Line 21 (index 20) contains the write_file_info flag (TRUE or FALSE).
    """
    try:
        # Read user_choice from line 19 (index 18)
        df_choice = pd.read_csv(file_path, skiprows=18, nrows=1, header=None)
        user_choice = int(df_choice.iloc[0, 0])

        # Read write_file_info from line 21 (index 20)
        df_write_info = pd.read_csv(file_path, skiprows=20, nrows=1, header=None)
        write_info_raw = str(df_write_info.iloc[0, 0]).strip().lower()
        write_file_info = write_info_raw in ['true', '1', 'yes']

        return user_choice, write_file_info

    except FileNotFoundError:
        print(f"Error: {file_path} not found. Using default values.")
        return 16, False

    except Exception as e:
        print(f"Error reading user data: {e}. Using default values.")
        return 16, False

