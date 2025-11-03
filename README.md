# Metalica - Metal Inventory Management System

A comprehensive metal inventory management application built with Python Tkinter. This system helps businesses track metal inventory, manage transactions (cash and credit), and maintain customer/supplier ledger pages.

## Features

- **Inventory Management**
  - Add new metals or add stock to existing metals
  - Track separate sources (lots) for each metal with quantity and purchase price
  - Sell/withdraw quantity with FIFO cost-basis calculation
  - Calculate profit per metal and total profit

- **Transaction Management**
  - Support for cash and credit transactions
  - Track partial payments (installments or partial amounts)
  - Maintain a unified transaction log
  - Calculate and display profit margins with percentage view

- **Customer/Supplier Management**
  - Individual ledger pages for each customer/supplier
  - Track all transactions with each party
  - Monitor outstanding balances (owed to business or by business)
  - View detailed transaction history per customer/supplier

- **Data Management**
  - Export/Import data in JSON/CSV formats
  - Automatic backups with AM/PM timestamps
  - Search functionality
  - History window with transaction details

- **User Interface**
  - Light and dark mode support
  - Modern, clean interface with vibrant colors
  - Responsive design
  - Arabic language support

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/metalica.git
   ```

2. Navigate to the project directory:
   ```bash
   cd metalica
   ```

3. Run the application:
   ```bash
   python metal_inventory.py
   ```

## Usage

1. **Adding Metals**
   - Use "➕ إضافة معدن" to add a new metal
   - Use "⬆️ إضافة لمعدن موجود" to add stock to an existing metal
   - Select from previous suppliers or add new ones

2. **Selling/Withdrawing**
   - Use "💰 بيع / سحب كمية" to record sales
   - Select from previous customers or add new ones
   - Enter payment details (partial payments supported)

3. **Managing Parties**
   - Use "👥 الحسابات" to view customer/supplier list
   - Double-click on a party to see their transaction history
   - Track outstanding balances

4. **Viewing History**
   - Use "🕒 السجل" to view all transactions
   - Double-click on a customer/supplier name to see their transaction history

5. **Deleting Metals**
   - Select a metal and click "🗑️ حذف معدن"
   - Note: This only deletes the metal, not associated transactions or parties

## Configuration

The application automatically creates:
- `data.json` - Main data file
- `backups/` - Directory for automatic backups
- `settings.json` - Application settings (theme preferences)

## File Structure

```
metalica/
├── metal_inventory.py    # Main application
├── data.json             # Data storage
├── settings.json         # User settings
├── backups/              # Automatic backup directory
└── README.md             # This file
```

## Requirements

- Python 3.6+
- Tkinter (usually included with Python)

## License

This project is open source and available under the MIT License.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

If you encounter any issues or have questions, please open an issue in the GitHub repository.

---

*Developed with ❤️ for metal inventory management*
