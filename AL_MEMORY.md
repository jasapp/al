# Al's Memory

This file contains everything Al knows about Okluma's supply chain.
Auto-updated as Al learns from conversations and invoices.

Last updated: 2025-10-11

---

## Products

### DC2 (Flagship Flashlight)

**Bill of Materials:**
- 1x 21mm sapphire lens
- 1x 21mm PTFE gasket
- 1x MCR20S driver
- 1x DC2 body (machined from titanium stock)
- 1x tailcap
- 1x battery (18650)
- Misc hardware (screws, O-rings)

**Manufacturing:**
- Machine time: 30 minutes per unit
- Titanium stock: 5.5 inches of 1" round per unit
- Copper stock: 1 inch of 7/8" round C145 per unit
- Historical scrap rate: 8%

**Notes:**
- DC2 engine assembly has intermittent reliability issues (added 2025-10-11)

---

## Vendors

*(Al will populate this as he learns from invoices)*

### Example Format:
```
Vendor Name: Shenzhen Precision Parts Co
Contact: Li Wei
Email: liwei@example.com
Products: PTFE gaskets, O-rings
Lead time: 3 weeks
Notes: Reliable but needs 2-week heads up for large orders
Last order: 2025-10-01 (200x PTFE gaskets @ $0.45/unit)
```

---

## Raw Materials

### Titanium 6Al4V - 1" Round
- Used for: DC1, DC2 body machining
- Reorder point: 200 inches
- Typical order: 500 inches
- Vendor: TBD
- Lead time: TBD

### Titanium 6Al4V - 3/4" Round
- Used for: DC0 body machining
- Reorder point: 100 inches
- Typical order: 200 inches
- Vendor: TBD
- Lead time: TBD

### Copper C145 - 7/8" Round
- Used for: DC series engines
- Reorder point: 100 inches
- Typical order: 200 inches
- Vendor: TBD
- Lead time: TBD

---

## Scrap History

*(Al tracks manufacturing waste here)*

### Format:
```
Date: 2025-10-11
Product: DC2
Quantity: 3 units
Reason: Chip mark stuck in collet
Material lost: 16.5" titanium, 3" copper
Time lost: 90 minutes
```

---

## Reorder Warnings

*(Al's active warnings and snooze states)*

### Format:
```
Component: Sapphire lenses 21mm
Current level: 15
Reorder point: 20
Last warned: 2025-10-09
Status: Snoozed until 2025-10-13 (user said "broke till Friday")
Vendor: TBD
Lead time: 3 weeks
```

---

## Incoming Inventory

*(Stuff that's been ordered but not received)*

### Format:
```
Order date: 2025-10-01
Vendor: Shenzhen Precision Parts Co
Items: 200x PTFE gaskets
Expected arrival: 2025-10-25
Status: In transit
```

---

## Notes

- Al gets progressively more annoyed if reorder warnings are ignored
- Mood resets when user actually orders the thing
- Production planning accounts for historical scrap rates
- All conversational - no commands to remember
