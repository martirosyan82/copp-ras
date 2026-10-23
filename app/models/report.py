"""app/models/report.py вЂ” РЁР°Р±Р»РѕРЅС‹, СЃРґР°РЅРЅС‹Рµ РѕС‚С‡С‘С‚С‹ Рё С‡РµСЂРЅРѕРІРёРєРё."""
from app.extensions import db
from sqlalchemy import JSON
from datetime import datetime
from app.models.files import report_attachments

class ReportTemplate(db.Model):
    """РЁР°Р±Р»РѕРЅ РѕС‚С‡С‘С‚Р°. РЎС‚СЂСѓРєС‚СѓСЂР° РїРѕР»РµР№ С…СЂР°РЅРёС‚СЃСЏ РІ schema (JSON)."""
    __tablename__ = 'report_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1024))
    short_name = db.Column(db.String(256))
    period = db.Column(db.String(128))
    period_data = db.Column(JSON, nullable=True)
    deadline = db.Column(db.Date)
    is_published = db.Column(db.Boolean, default=False)
    is_completed = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    is_template = db.Column(db.Boolean, default=False)
    schema = db.Column(JSON)
    attachments = db.relationship(
        'UploadedFile', secondary=report_attachments,
        backref=db.backref('reports', lazy='dynamic')
    )

class ReportSubmission(db.Model):
    """Р—Р°РїРѕР»РЅРµРЅРЅС‹Р№ РѕС‚С‡С‘С‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ."""
    __tablename__ = 'report_submissions'
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('report_templates.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    data = db.Column(JSON)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    is_revision = db.Column(db.Boolean, default=False)
    revision_comment = db.Column(db.Text, nullable=True)
    returned_at = db.Column(db.DateTime, nullable=True)
    returned_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    template = db.relationship('ReportTemplate', backref='submissions')
    user = db.relationship('User', foreign_keys=[user_id], backref='submissions')
    returned_by = db.relationship('User', foreign_keys=[returned_by_id])

class ReportDraft(db.Model):
    """РћР±Р»Р°С‡РЅС‹Р№ С‡РµСЂРЅРѕРІРёРє РѕС‚С‡С‘С‚Р°. РћРґРёРЅ РЅР° РїР°СЂСѓ (user, template)."""
    __tablename__ = 'report_drafts'
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('report_templates.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    data = db.Column(JSON)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('template_id', 'user_id', name='uq_draft_template_user'),)
    template = db.relationship('ReportTemplate', backref='drafts')
    user = db.relationship('User', backref='drafts')

class ManualRow(db.Model):
    """
    Р СѓС‡РЅС‹Рµ СЃС‚СЂРѕРєРё РІ СЃРІРѕРґРЅРѕР№ С‚Р°Р±Р»РёС†Рµ РґР»СЏ РѕСЂРіР°РЅРёР·Р°С†РёР№, РєРѕС‚РѕСЂС‹С… РЅРµС‚ РІ СЃРёСЃС‚РµРјРµ.
    РќРµ РїСЂРёРІСЏР·Р°РЅС‹ Рє СѓС‡С‘С‚РЅРѕР№ Р·Р°РїРёСЃРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.
    """
    __tablename__ = 'manual_rows'
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('report_templates.id'), nullable=False)
    org_name = db.Column(db.String(256), nullable=False)
    subgroup = db.Column(db.String(100), nullable=True)
    data = db.Column(JSON, default=dict)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template = db.relationship('ReportTemplate', backref=db.backref('manual_rows', cascade='all, delete-orphan'))
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

