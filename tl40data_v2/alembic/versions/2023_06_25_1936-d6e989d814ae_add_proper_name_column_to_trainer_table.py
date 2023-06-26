"""Add proper_name column to trainer table

Revision ID: d6e989d814ae
Revises: 24bfd9e04f7c
Create Date: 2023-06-25 19:36:29.196345

"""
from alembic import op
import sqlalchemy as sa

from tables import Trainer

# revision identifiers, used by Alembic.
revision = 'd6e989d814ae'
down_revision = '24bfd9e04f7c'
branch_labels = None
depends_on = None

# Define the new columns for the trainer table
proper_name_column = sa.Column('proper_name', sa.String)  # TODO need nullable?
name_column = sa.Column('name', sa.String)


def upgrade():
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    
    # Add the new columns to the trainer table
    op.add_column('trainer', proper_name_column)
    session.commit()
    
    ## Set the proper_name column using the values from the name column
    #session.execute(
    #    sa.update(sa.table('trainer')).values(proper_name=sa.func.upper(name_column))
    #)
    #session.commit()
    
    ## Update the name column to lowercase
    #session.execute(
    #    sa.update(sa.table('trainer')).values(name=sa.func.lower(name_column))
    #)
    #session.commit()

    # Set the proper_name column using the values from the existing name column
    #session.execute(
    #    sa.update(sa.table('trainer')).values(proper_name=sa.func.upper(sa.column('name')))
    #)
    #session.commit()
    
    # Update the name column to lowercase
    session.execute(
        #sa.update(sa.table('trainer')).values(name=sa.func.lower(sa.column('name')))
        #sa.update(sa.table('trainer')).values(name=sa.func.lower(sa.text('name')))
        #sa.update(sa.table('trainer')).values(name=sa.func.lower(sa.text('name')))
        #sa.update(sa.table('trainer')).values(name='wtf')
        #'UPDATE "trainer" set proper_name = "wtf"'
        #sa.update('trainer').values(proper_name="abcd")
        #sa.update(Trainer).values(proper_name=name_column)  # works!
        sa.update(Trainer).values(proper_name=name_column)
    )
    session.execute(
        sa.update(Trainer).values(name=sa.func.lower(name_column))
    )
    session.commit()


def downgrade():
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    
    # Remove the new columns from the trainer table
    op.drop_column('trainer', 'proper_name')

    session.commit()
