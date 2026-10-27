"""Somatropin unit behavior and migration regression checks."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.db import Base
from app.models import Compound, Purchase, Vial
from app.migrations import migrate
from app import units as U
from app.routers.compounds import create_compound
from app.routers.purchases import add_vials
from datetime import date


def test_iu_concentration_and_draw_arithmetic():
    base, dim = U.to_base(36, "IU")
    assert (base, dim) == (36, "iu")
    assert U.fmt_amount(base, dim) == "36 IU"
    assert U.fmt_conc(U.concentration(base, 3), dim) == "12 IU/mL"
    assert U.amount_to_vial_base(0.25, "mL", dim, 12) == 3


def test_compound_defaults_to_iu_and_purchase_tracks_iu(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tracker.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        create_compound(name="Somatropin (HGH)", category="peptide", notes="", primary_unit="mg", db=db)
        c = db.scalar(select(Compound).where(Compound.name == "Somatropin (HGH)"))
        assert c.primary_unit == "IU"
        p = Purchase(vendor="Example", purchased_on=date.today())
        db.add(p)
        db.commit()
        response = add_vials(pid=p.id, compound_id=c.id, quantity=2, content_value="36",
                             content_unit="IU", unit_price="25", kit_size=1, kit_count=1, volume_ml="", concentration="", form="lyophilized", label="", lot="", expires_on="", notes="", cap_color="", db=db)
        assert response.status_code == 303
        vials = list(db.scalars(select(Vial).where(Vial.compound_id == c.id)))
        assert len(vials) == 2, response.headers.get("location")
        assert all(v.content_unit == "IU" and v.content_value == 36 for v in vials)
        add_vials(pid=p.id, compound_id=c.id, quantity=1, content_value="12",
                  content_unit="mg", kit_size=1, kit_count=1, volume_ml="", concentration="", form="lyophilized", label="", lot="", expires_on="", notes="", cap_color="", db=db)
        assert len(list(db.scalars(select(Vial).where(Vial.compound_id == c.id)))) == 2
    engine.dispose()


def test_existing_iu_vials_migrate_without_unit_change(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tracker.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        c = Compound(name="Somatropin", category="peptide", notes="", primary_unit="mg")
        db.add(c)
        db.flush()
        db.add(Vial(compound_id=c.id, content_value=36, content_unit="IU"))
        db.commit()
    migrate(engine)
    with Session(engine) as db:
        assert db.get(Compound, 1).primary_unit == "IU"
        assert db.scalar(select(Vial)).content_unit == "IU"
    engine.dispose()
