"""Reporting periods, and the period each one is compared with.

A figure with no period cannot be judged: "1.2 tỷ collected" is good or bad
depending on whether it is this month or since the company opened, and the
reports used to show only the second. Every period here has a previous one of
the same length, so a report can say whether things are getting better.

Dates are half-open: `start <= day < end`.
"""
from dataclasses import dataclass
from datetime import date

PERIOD_KEYS = ('month', 'last_month', 'quarter', 'year', 'all')
PERIOD_LABELS = {
    'month': 'Tháng này',
    'last_month': 'Tháng trước',
    'quarter': 'Quý này',
    'year': 'Năm nay',
    'all': 'Toàn bộ',
}


@dataclass(frozen=True)
class Period:
    key: str
    start: date | None   # None = since the beginning
    end: date | None     # None = open-ended

    @property
    def label(self):
        return PERIOD_LABELS[self.key]

    @property
    def last_day(self):
        """The last day IN the period — `end` is exclusive, people read inclusive."""
        from datetime import timedelta
        return self.end - timedelta(days=1) if self.end else None

    def contains(self, day):
        if day is None:
            return False
        return (self.start is None or day >= self.start) and (self.end is None or day < self.end)


def _month_start(day):
    return day.replace(day=1)


def _add_months(day, months):
    index = day.month - 1 + months
    return day.replace(year=day.year + index // 12, month=index % 12 + 1, day=1)


def period(key, today=None):
    """The period called `key`, as of `today`. Unknown keys mean this month."""
    today = today or date.today()
    if key == 'all':
        return Period('all', None, None)
    if key == 'last_month':
        this = _month_start(today)
        return Period('last_month', _add_months(this, -1), this)
    if key == 'quarter':
        start = today.replace(month=(today.month - 1) // 3 * 3 + 1, day=1)
        return Period('quarter', start, _add_months(start, 3))
    if key == 'year':
        return Period('year', date(today.year, 1, 1), date(today.year + 1, 1, 1))
    start = _month_start(today)
    return Period('month', start, _add_months(start, 1))


def previous(p):
    """The period of the same length just before `p` — None for 'all'.

    'This month' is compared with the whole of last month even while this one
    is still running; the comparison is labelled, so the reader knows.
    """
    if p.start is None:
        return None
    months = (p.end.year - p.start.year) * 12 + (p.end.month - p.start.month)
    return Period(p.key, _add_months(p.start, -months), p.start)

