from flask_script import Manager
from app import create_app
from config import DevelopConfig
from models import db
from flask_migrate import Migrate, MigrateCommand
app = create_app(DevelopConfig)
manager = Manager(app)
db.init_app(app)
Migrate(app, db)
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()
