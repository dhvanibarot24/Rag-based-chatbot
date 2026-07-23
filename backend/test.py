from rag import search

# For manual CLI testing, enter the numeric user_id whose documents you want
# to search (matches the id column in the users table).
user_id = int(input("User ID: "))
q = input("Ask: ")

print(search(q, history=[], user_id=user_id))