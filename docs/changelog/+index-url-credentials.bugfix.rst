Remove the user name and password from index URLs before ``from-index`` hands them to Nab, which never sends them, so
resolver errors no longer print them.
