#!/usr/bin/env python
import os
import logging
from datetime import datetime

import webapp2
import jinja2

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.api import mail

import urllib, hashlib


jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + '/templates'))

class Person(db.Model):
    user = db.UserProperty()
    updated = db.DateTimeProperty(auto_now=True)
    added = db.DateTimeProperty(auto_now_add=True)
    active = db.BooleanProperty()
    first_name = db.StringProperty()
    last_name = db.StringProperty()
    phone_number = db.PhoneNumberProperty()
    address = db.PostalAddressProperty()
    email = db.EmailProperty()
    twitter = db.StringProperty()
    github = db.StringProperty()
    linkedin = db.StringProperty()
    facebook = db.StringProperty()
    gravatar = db.LinkProperty()

    @classmethod
    def get_by_user(cls, user):
        return cls.all().filter("user = ", user).get()

    @classmethod
    def get_for_current_user(cls):
        return cls.get_by_user(users.get_current_user())

    @property
    def invitations(self):
        return Invitation.get_by_inviter(self.user)

class Invitation(db.Model):
    inviter = db.UserProperty()
    email = db.EmailProperty()
    created_at = db.DateTimeProperty(auto_now_add=True)
    claimed_at = db.DateTimeProperty()

    @classmethod
    def get_by_email(cls, email):
        return cls.all().filter("email = ", email).get()

    @classmethod
    def get_by_inviter(cls, user):
        return cls.all().filter("inviter = ", user).run()

class MainHandler(webapp2.RequestHandler):
    def get(self):
    	user = users.get_current_user()
    	if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'

            person = Person.get_by_user(user)

            if person:
                logging.info('Using person %s' % person)
                self.redirect('/people')
                return
            else:
                if users.is_current_user_admin():
                    person = Person()
                    person.user = user
                    person.put()
                    logging.info('Adding person for admin user %s.' % user)
                    self.redirect('/people')
                    return

                logging.info('No person for user %s' % user)
                self.redirect(url)

        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = {
            'url': url,
            'url_linktext': url_linktext,
        }

        template = jinja_environment.get_template('index.html')
        self.response.out.write(template.render(template_values))

class PeopleHandler(webapp2.RequestHandler):
    def get(self):
        person = Person.get_for_current_user()

        if not person:
            self.redirect('/')
            return

        url = users.create_logout_url('/')
        url_linktext = 'Logout'

        people = Person.all().filter('active = ',True) #.run()

        template_values = {
            'url': url,
            'url_linktext': url_linktext,
            'people': people,
        }

        template = jinja_environment.get_template('people.html')
        self.response.out.write(template.render(template_values))

class MyselfHandler(webapp2.RequestHandler):
    def get(self):
        person = Person.get_for_current_user()

        if not person:
            self.redirect('/')
            return

        url = users.create_logout_url('/')
        url_linktext = 'Logout'

        template_values = {
            'url': url,
            'url_linktext': url_linktext,
            'myself': person,
        }

        template = jinja_environment.get_template('myself.html')
        self.response.out.write(template.render(template_values))

    def post(self):
        person = Person.get_for_current_user()

        if not person:
            self.redirect('/')
            return
        person.first_name = self.request.get('first_name') if self.request.get('first_name') else None
        person.last_name = self.request.get('last_name') if self.request.get('last_name') else None
        person.address = self.request.get('address') if self.request.get('address') else None
        person.phone_number = self.request.get('phone_number') if self.request.get('phone_number') else None
        person.email = self.request.get('email') if self.request.get('email') else None
        person.twitter = self.request.get('twitter') if self.request.get('twitter') else None
        person.github = self.request.get('github') if self.request.get('github') else None
        person.linkedin = self.request.get('linkedin') if self.request.get('linkedin') else None
        person.facebook = self.request.get('facebook') if self.request.get('facebook') else None


        if person.email:
            gravatar_url = "http://www.gravatar.com/avatar.php?"
            gravatar_url += urllib.urlencode({'gravatar_id':hashlib.md5(person.email.lower()).hexdigest(), 'size':str(40)})
            person.gravatar = gravatar_url
        else:
            person.gravatar = None


        if person.first_name is not None and person.last_name is not None :
            person.active = True

        person.put()

        self.redirect('/people/me')

class InviteHandler(webapp2.RequestHandler):
    def get(self):
        person = Person.get_for_current_user()

        if not person:
            self.redirect('/')
            return

        url = users.create_logout_url('/')
        url_linktext = 'Logout'

        template_values = {
            'url': url,
            'url_linktext': url_linktext,
            'invite_root': self.request.application_url,
            'myself': person,
            'invitations': person.invitations,
        }

        template = jinja_environment.get_template('invite.html')
        self.response.out.write(template.render(template_values))

    def post(self):
        user = users.get_current_user()
        person = Person.get_for_current_user()

        if not person:
            self.redirect('/')
            return

        invited_email = self.request.get('email')

        existing_invitation = Invitation.get_by_email(invited_email)

        if existing_invitation:
            logging.warn('Ignoring already-invited e-mail %s.' % invited_email)
        else:
            invitation = Invitation()
            invitation.email = invited_email
            invitation.inviter = users.get_current_user()
            invitation.put()

            if not mail.is_email_valid(invited_email):
                logging.warn('Ignoring invalid e-mail %s.' % invited_email)
            else:
                message = mail.EmailMessage()
                message.sender = user.email()
                message.to = invited_email
                message.subject = "You've Been Invited to OFA Tech Alumni"
                message.body = """I've invited you to participate in the OFA Tech Alumni website!

Sign up to share your contact information and make it easier to stay in contact with your fellow OFA Tech coworkers.

Use this link to join:

%s/invited?key=%s""" % (self.request.application_url, invitation.key())

                message.send()

        self.redirect('/people/invite')

class InvitedHandler(webapp2.RequestHandler):
    def get(self):
        invitation = Invitation.get(self.request.get('key'))

        if invitation:
            if invitation.claimed_at:
                logging.warn('Attempt to use claimed invitation %s.' % invitation.key())
                self.redirect('/')
                return
        else:
            self.redirect('/')
            return

        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return

        invitation.claimed_at = datetime.utcnow()
        invitation.put()

        person = Person()
        person.user = user
        person.email = invitation.email
        person.put()

        self.redirect('/people/me')

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/people', PeopleHandler),
    ('/people/me', MyselfHandler),
    ('/people/invite', InviteHandler),
    ('/invited', InvitedHandler)
], debug=True)
