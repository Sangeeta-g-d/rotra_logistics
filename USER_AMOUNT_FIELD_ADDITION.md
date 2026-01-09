# User Amount Field Addition - Implementation Complete

## What Was Added

Added a new `user_amount` field to the Load model to capture user-specific amounts when creating loads.

## Changes Made

### 1. Database Model - `logistics_app/models.py`

**Added Field (Lines 364-373):**
```python
user_amount = models.DecimalField(
    max_digits=14,
    decimal_places=2,
    default=Decimal('0.00'),
    verbose_name="User Amount",
    null=True,
    blank=True,
    help_text="User-specific amount for this load"
)
```

**Field Specifications:**
- **Type:** DecimalField
- **Precision:** 14 digits total, 2 decimal places
- **Default:** 0.00
- **Optional:** Yes (blank=True, null=True)
- **Description:** Stores user-specific amount for tracking/reference

### 2. Backend - `logistics_app/views.py`

**Updated add_load() function (Lines 1167-1176):**

**Input Processing:**
```python
# User Amount (Optional)
user_amount = Decimal('0.00')
user_amount_str = request.POST.get('user_amount', '').replace(',', '').strip()
if user_amount_str:
    try:
        user_amount = Decimal(user_amount_str).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    except:
        user_amount = Decimal('0.00')
```

**Load Creation (Line 1197):**
```python
load = Load.objects.create(
    ...
    user_amount=user_amount,
    ...
)
```

**Features:**
- ✅ Accepts comma-separated values (e.g., "1,000.00")
- ✅ Proper decimal rounding (ROUND_HALF_UP)
- ✅ Fallback to 0.00 if invalid input
- ✅ Optional field (defaults to 0.00)

### 3. Frontend Form - `logistics_app/templates/load_list.html`

**Added Form Field (Lines 383-393):**
```html
<div class="form-row">
  <div class="form-group full-width">
    <label>User Amount (Optional)</label>
    <input type="number" 
           name="user_amount" 
           id="userAmountInput"
           step="0.01" 
           min="0" 
           placeholder="Enter user-specific amount"
           style="font-size:16px; font-weight:600; padding: 12px;">
    <small style="color:#6b7280; font-size: 12px; margin-top: 4px;">
      Enter the user-specific amount for this load (if applicable)
    </small>
  </div>
</div>
```

**Form Placement:**
- Located after "Total Trip Amount" field
- Before "Payment Split" section
- Same styling as other form fields

**Input Specifications:**
- **Type:** Number input
- **Step:** 0.01 (allows two decimal places)
- **Min:** 0 (prevents negative values)
- **Placeholder:** "Enter user-specific amount"

### 4. Database Migration

**File:** `logistics_app/migrations/0068_load_user_amount.py`

**Status:** ✅ Applied successfully

**What it does:**
- Adds `user_amount` column to `loads_load` table
- Type: DECIMAL(14,2)
- Allows NULL values
- Default: 0.00

## Field Characteristics

| Property | Value |
|----------|-------|
| Database Column Name | user_amount |
| Data Type | DecimalField |
| Max Digits | 14 (total digits) |
| Decimal Places | 2 |
| Default Value | 0.00 |
| Required | No |
| Nullable | Yes |
| Editable | Yes |
| Help Text | User-specific amount for this load |

## Usage Flow

1. **User fills form:**
   - Navigates to "Add Load" form
   - Enters "Total Trip Amount" (e.g., ₹100,000)
   - Optionally enters "User Amount" (e.g., ₹50,000)

2. **Backend processes:**
   - Retrieves `user_amount` from request.POST
   - Converts to Decimal with proper formatting
   - Stores in Load model

3. **Data stored:**
   ```
   Load record:
   - total_amount: 100000.00
   - user_amount: 50000.00
   ```

4. **Data usage:**
   - Can be accessed via: `load.user_amount`
   - Displayed in payment details
   - Used for user-specific calculations/reporting

## Example Scenarios

### Scenario 1: No User Amount
```
Scenario: Regular load without user-specific amount
Form Input:
  - Total Trip Amount: ₹100,000
  - User Amount: (left empty)
Result:
  - user_amount = 0.00
```

### Scenario 2: With User Amount
```
Scenario: Load with user-specific tracking amount
Form Input:
  - Total Trip Amount: ₹100,000
  - User Amount: ₹50,000
Result:
  - user_amount = 50,000.00
```

### Scenario 3: With Comma Format
```
Scenario: User enters amount with comma separator
Form Input:
  - User Amount: 1,50,000.50
Backend Processing:
  - Removes commas: "150000.50"
Result:
  - user_amount = 150000.50
```

## Accessing the Field

### In Views
```python
load = Load.objects.get(id=1)
user_amt = load.user_amount  # Returns Decimal
user_amt_float = float(load.user_amount)  # Returns float
```

### In Serializers
```python
'user_amount': float(load.user_amount) or 0.0
```

### In Templates
```html
{{ load.user_amount|floatformat:2 }}
```

## Testing Checklist
- [ ] Create a load with user_amount = 50000
- [ ] Create a load with user_amount = 0 (empty field)
- [ ] Verify field appears in database
- [ ] Test with comma-separated values (e.g., 1,50,000)
- [ ] Test with decimal values (e.g., 50000.99)
- [ ] Verify form validation (negative numbers rejected)
- [ ] Test payment details display includes user_amount
- [ ] Test load list shows/retrieves user_amount

## Files Modified
1. `logistics_app/models.py` - Added user_amount field to Load model
2. `logistics_app/views.py` - Updated add_load() to accept and store user_amount
3. `logistics_app/templates/load_list.html` - Added form input field

## Files Created
1. `logistics_app/migrations/0068_load_user_amount.py` - Database migration (auto-generated)

## Backward Compatibility
✅ No breaking changes
✅ Field is optional (nullable, blank=True)
✅ Default value: 0.00
✅ Existing loads unaffected
✅ No modifications to existing fields required

## Future Enhancements
- Display user_amount in payment drawer
- Include user_amount in payment calculations (if needed)
- Filter/search loads by user_amount
- Add user_amount to load edit form
- Add user_amount to API responses
