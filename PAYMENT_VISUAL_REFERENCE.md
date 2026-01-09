# Payment Management - Visual Reference Guide

## Filter Buttons Location & Functionality

```
┌─────────────────────────────────────────────────────────────────┐
│                   Payment Management                             │
│  Search: [_________________]  [View All Loads]                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [All Payments]  [Advance Paid]  [Pending]  [Paid]             │
│  (Green active)   (Default grey)  (Grey)    (Grey)             │
│                                                                  │
│  Filters active: Shows/hides rows based on payment status       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Payment Status Meanings

### 1. **PENDING** 🕐 (Orange)
- No payments made yet
- First half not paid
- Second half not paid
- Status: `first_half_payment_paid = false`

### 2. **ADVANCE PAID** ⏳ (Blue)
- First half (90%) payment completed
- Second half (10%) still pending
- Status: `first_half_payment_paid = true` AND `trip_status != 'payment_completed'`

### 3. **PAID** ✓ (Green)
- Both first half and second half paid
- Payment completed
- Status: `first_half_payment_paid = true` AND `trip_status = 'payment_completed'`

---

## Table Structure

```
┌──────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────┐
│ Load ID  │ Route        │ Payment Stat │ First Half   │ Second Half  │ Total Amount │ Actions  │
├──────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────┤
│ LD-001   │ Mumbai → Delhi│ ✓ Paid      │ ₹90,000 ✓   │ ₹10,000 ✓   │ ₹100,000     │ View Pmt │
│          │              │ (Green box)  │ (Green)      │ (Green)      │ Total charges│          │
├──────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────┤
│ LD-002   │ Delhi → Pune │ ⏳ Advance   │ ₹85,000 ✓   │ ₹9,445 ⏳   │ ₹95,000      │ View Pmt │
│          │              │ (Blue box)   │ (Green)      │ (Orange)     │ Total charges│          │
├──────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────┤
│ LD-003   │ Pune → Mumbai│ ⏳ Pending   │ ₹81,000 ⏳  │ ₹9,000 ⏳   │ ₹92,000      │ View Pmt │
│          │              │ (Orange box) │ (Orange)     │ (Orange)     │ Total charges│          │
└──────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────┘
```

---

## Payment Details Drawer

```
┌─────────────────────────────────────────────────────────────┐
│ LD-001 [✓ Payment Completed]                           [✕]  │
├─────────────────────────────────────────────────────────────┤
│ Route: Mumbai ⟷ Delhi                                      │
├─────────────────────────────────────────────────────────────┤
│ Trip Information                                            │
│ • Vehicle: MH-01-AB-1234  Driver: John Doe                 │
│ • Type: 10-Ton Truck      Distance: 1,400 km               │
│ • Start: 15 Jan, 2025     ETA: 18 Jan, 2025               │
│ 📍 Current Location: On Route                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ ╔════════════════════════════════════════════════════════╗  │
│ ║ Payment Summary                    ✓ PAID              ║  │
│ ╚════════════════════════════════════════════════════════╝  │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ First Half (90%)      │ Second Half (10%)           │   │
│  │ ₹90,000              │ ₹10,000                      │   │
│  │ ✓ Paid               │ ✓ Paid                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│ ╔════════════════════════════════════════════════════════╗  │
│ ║ 🕐 Holding Charges                                     ║  │
│ ╚════════════════════════════════════════════════════════╝  │
│                                                              │
│  Unloading Stage                                            │
│  Amount: ₹500  |  Reason: Delayed delivery                │
│  Added by: Admin  |  16 Jan, 2025, 3:30 PM                │
│                                                              │
│  Customs Clearance                                          │
│  Amount: ₹300  |  Reason: Documentation delay             │
│  Added by: Traffic  |  17 Jan, 2025, 9:15 AM              │
│                                                              │
│ ╔════════════════════════════════════════════════════════╗  │
│ ║ % TDS Deduction                                        ║  │
│ ╚════════════════════════════════════════════════════════╝  │
│                                                              │
│  TDS Rate: 2.00%                                            │
│  TDS Amount: ₹200 (deducted from second half)              │
│  After TDS: ₹9,800 ✓                                       │
│                                                              │
│ ╔════════════════════════════════════════════════════════╗  │
│ ║ Payment Breakdown                                      ║  │
│ ╚════════════════════════════════════════════════════════╝  │
│                                                              │
│  Total Freight        ₹100,000                             │
│  + Holding Charges      ₹800                               │
│  - TDS Deduction       (₹200)                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━                                │
│  TOTAL AMOUNT DUE    ₹100,600 ✓                            │
│                                                              │
│ ╔════════════════════════════════════════════════════════╗  │
│ ║ ✓ Payment Timeline                                     ║  │
│ ╚════════════════════════════════════════════════════════╝  │
│                                                              │
│  Advance Paid On:     15 Jan, 2025, 10:00 AM              │
│  Final Paid On:       18 Jan, 2025, 04:30 PM              │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│ Customer Details                                            │
│ • Customer: ABC Logistics Pvt Ltd                           │
│ • Phone: +91-9876543210                                     │
│ • Contact: Mr. Rajesh Kumar                                 │
│ • Phone: +91-9876543211                                     │
│                                                              │
│ Vendor Details                                              │
│ • Vendor: XYZ Transport Co                                  │
│ • Phone: +91-9876543212                                     │
│                                                              │
│ Driver Details                                              │
│ • Driver: John Doe                                          │
│ • Phone: +91-9876543213                                     │
│                                                              │
│ Trip Progress: 100% Complete                                │
│ ████████████████████ 100%                                   │
│                                                              │
│ Timeline                                                    │
│ ✓ Pending (15 Jan)          Trip Requested                 │
│ ✓ Confirmed (15 Jan)        Confirmed by vendor            │
│ ✓ Loaded (15 Jan)           Reached loading point          │
│ ✓ LR Uploaded (15 Jan)       Loading receipt uploaded      │
│ ✓ In Transit (15 Jan)        Vehicle on route              │
│ ✓ Unloading (18 Jan)         Reached unloading point       │
│ ✓ POD Uploaded (18 Jan)      Proof of delivery uploaded    │
│ ✓ Payment Completed (18 Jan) Final payment processed       │
│                                                              │
│ Chat                                                        │
│ [Messages will appear here]                                 │
│                                                              │
│ [Update Status] [Upload LR] [Upload POD] [Add Comment]     │
│ [Close Trip]                                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Color Coding Guide

### Payment Status Colors
```
GREEN  (#d1fae5)  → ✓ Paid
BLUE   (#dbeafe)  → ⏳ Advance Paid
ORANGE (#fef3c7)  → ⏳ Pending
```

### Section Colors
```
LIGHT BLUE      → Payment Status Overview (Primary)
ORANGE/AMBER    → Holding Charges Section
YELLOW          → TDS Deduction Section
INDIGO          → Payment Adjustment Section
LIGHT GRAY      → Payment Breakdown Section
LIGHT GREEN     → Payment Timeline Section
```

---

## How Filters Work

### Filter Click Flow
```
User clicks [Pending] button
    ↓
filterByPaymentStatus('pending') called
    ↓
All rows with data-payment-status != 'pending' are hidden
Rows with data-payment-status = 'pending' are shown
    ↓
Button styling updated (green highlight)
    ↓
Pagination recalculated for visible rows
    ↓
User sees only pending payments
```

### Example Scenarios

#### Scenario 1: Show Only Paid Payments
- Click [Paid] button
- Shows: All rows where `payment_status = 'paid'`
- Table displays only trips with both halves paid

#### Scenario 2: Show Advance Paid Payments
- Click [Advance Paid] button
- Shows: All rows where `payment_status = 'advance_paid'`
- Table displays only trips with first half paid, second half pending

#### Scenario 3: Show All Payments
- Click [All Payments] button (default)
- Shows: All rows regardless of payment status
- Full table visible

---

## Payment Data Calculation

### Payment Status Determination
```javascript
if (first_half_payment_paid && trip_status == 'payment_completed') {
    status = 'PAID'
} else if (first_half_payment_paid) {
    status = 'ADVANCE_PAID'
} else {
    status = 'PENDING'
}
```

### Total Amount Calculation
```javascript
total_amount_due = total_freight
                 + holding_charges (if > 0)
                 - tds_amount (if apply_tds = true)
                 + adjustment_amount (if adjusted)
```

### TDS Calculation (if apply_tds = true)
```javascript
tds_rate = 2.00% (default from TDSRate model)
tds_amount = second_half_payment * (tds_rate / 100)
after_tds = second_half_payment - tds_amount
```

---

## API Response Example

```json
{
  "success": true,
  "data": {
    "load_id": "LD-001",
    "first_half_payment": 90000,
    "second_half_payment": 10000,
    "first_half_payment_paid": true,
    "first_half_payment_paid_at": "15 Jan, 2025 10:00 AM",
    "final_payment_paid": true,
    "final_payment_date": "18 Jan, 2025 04:30 PM",
    "trip_status": "payment_completed",
    "apply_tds": true,
    "tds_rate": 2.00,
    "tds_amount": 200,
    "tds_deductible_amount": 9800,
    "holding_charges": 800,
    "holding_charges_list": [
      {
        "id": 1,
        "amount": 500,
        "trip_stage": "unloading",
        "trip_stage_display": "Unloading",
        "reason": "Delayed delivery",
        "added_by": "Admin User",
        "created_at": "16 Jan, 2025 3:30 PM",
        "created_at_display": "16 Jan 2025, 3:30 PM"
      }
    ],
    "adjustment_amount": 0,
    "adjustment_type": "none",
    "payment_adjustment_reason": null,
    "total_amount": 100000,
    "customer_name": "ABC Logistics",
    "vendor_name": "XYZ Transport"
  }
}
```

---

## Mobile Responsiveness

### Tablet (768px and above)
- All features fully visible
- Filters in single row
- Full table columns displayed

### Mobile (below 768px)
- Filters stack vertically
- Table columns compress
- Drawer adapts to screen width
- Swipe to close drawer

---

## Key Takeaways

1. **Three Payment Statuses**: Pending → Advance Paid → Paid
2. **Four Filter Options**: All, Advance Paid, Pending, Paid
3. **Six Information Sections**: Status, Charges, TDS, Adjustments, Breakdown, Timeline
4. **Color-Coded**: Green=Paid, Blue=Advance, Orange=Pending
5. **Complete Transparency**: Every charge justified, every deduction explained
6. **Reference All Models**: Load, TDSRate, HoldingCharge included
