# dbaf
DBAF (https://previ.obspm.fr/dbaf) is a database collecting the measurements of radiations performed on flights. 
It has been designed by Paris Observatory and IRSN

# deploy
In production context : 
- you have to update the variables SECRET_KEY, DEBUG and ALLOWED_HOSTS in the dbaf/settings.py file
- you have to provide a db.sqlite3 file in the root directory

