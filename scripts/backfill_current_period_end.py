"""Backfill current_period_end for subscriptions that have NULL in DB by fetching from Stripe.

Usage:
  python scripts/backfill_current_period_end.py

This will:
 - find rows in subscriptions where stripe_subscription_id is not null and current_period_end is null
 - call Stripe to retrieve subscription and update current_period_end
 - print a summary

Requires STRIPE_SECRET_KEY in env or configured in app.core.config.Settings
"""
import os
from datetime import datetime
from app.db.session import SessionLocal
from app.models.subscription import Subscription
from app.services.billing import retrieve_subscription


def ensure_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        # assume UTC
        import pytz
        return dt.replace(tzinfo=pytz.UTC)
    return dt


def main():
    db = SessionLocal()
    try:
        rows = db.query(Subscription).filter(Subscription.stripe_subscription_id.isnot(None), Subscription.current_period_end.is_(None)).all()
        print(f'Found {len(rows)} subscriptions to backfill')
        updated = 0
        for r in rows:
            sid = r.stripe_subscription_id
            print('Fetching', sid)
            sub = retrieve_subscription(stripe_subscription_id=sid)
            if not sub:
                print('  -> stripe retrieve failed')
                continue
            # sub may be dict-like or stripe object
            # try dict-like access first, else attribute access
            cpe = None
            try:
                cpe = sub.get('current_period_end')
            except Exception:
                try:
                    cpe = getattr(sub, 'current_period_end', None)
                except Exception:
                    cpe = None
            # if not on top-level, check subscription items
            if not cpe:
                try:
                    items = sub.get('items', {}).get('data', [])
                except Exception:
                    items = getattr(sub, 'items', None)
                try:
                    for it in items or []:
                        try:
                            cpe = it.get('current_period_end')
                        except Exception:
                            cpe = getattr(it, 'current_period_end', None)
                        if cpe:
                            break
                except Exception:
                    pass
            if not cpe:
                # print a short debug dump so we can inspect what the Stripe object contains
                try:
                    # try to convert to dict if stripe object supports it
                    d = dict(sub)
                except Exception:
                    try:
                        d = {k: getattr(sub, k) for k in dir(sub) if not k.startswith('_')}
                    except Exception:
                        d = repr(sub)
                print('  -> stripe subscription object dump (truncated):')
                s = str(d)
                print(s[:2000])
            if cpe:
                try:
                    cpe_dt = datetime.utcfromtimestamp(int(cpe))
                    r.current_period_end = cpe_dt
                    db.add(r)
                    db.commit()
                    updated += 1
                    print('  -> updated', r.id, cpe_dt)
                except Exception as e:
                    print('  -> failed to parse/update', e)
            else:
                print('  -> no current_period_end on stripe subscription')
        print('Done. Updated', updated)
    finally:
        db.close()

if __name__ == '__main__':
    main()
