from app.extensions import db

class UserEconomy( db.Model ):
    user_id = db.Column( db.BigInteger, db.ForeignKey( "user.id" ), primary_key = True, nullable = False )
    robux_bal = db.Column( db.BigInteger, nullable = False, default = 0 )
    tickets_bal = db.Column( db.BigInteger, nullable = False, default = 0 )

    def __init__( self, user_id, robux_bal = 0, tickets_bal = 0 ):
        self.user_id = user_id
        self.robux_bal = robux_bal
        self.tickets_bal = tickets_bal

    def __repr__( self ):
        return f"<UserEconomy user_id={self.user_id} robux_bal={self.robux_bal} tickets_bal={self.tickets_bal}>"