"""Verify weather data quality and plot time series."""

import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


def verify_weather_data(csv_path: Path):
    """Load and verify weather data, create diagnostic plots."""
    
    df = pd.read_csv(csv_path)
    
    print(f"\n{'='*60}")
    print(f"Verifying: {csv_path.name}")
    print(f"{'='*60}\n")
    
    # Basic checks
    print("1. Data Completeness:")
    print(f"   Total rows: {len(df)}")
    print(f"   Expected: 8760 (hourly) or 8784 (leap year)")
    
    if len(df) not in [8760, 8784]:
        print("   ⚠ WARNING: Row count doesn't match expected hourly year!")
    
    print(f"\n2. Column Check:")
    required_cols = ['time_index', 'datetime', 'T_amb_C', 'RH_amb_pct', 'GHI_Wm2', 'wind_speed_ms']
    for col in required_cols:
        status = "✓" if col in df.columns else "✗ MISSING"
        print(f"   {col}: {status}")
    
    print(f"\n3. Value Ranges:")
    print(f"   Temperature: {df['T_amb_C'].min():.1f} to {df['T_amb_C'].max():.1f} °C")
    print(f"   RH: {df['RH_amb_pct'].min():.1f} to {df['RH_amb_pct'].max():.1f} %")
    print(f"   GHI: {df['GHI_Wm2'].min():.0f} to {df['GHI_Wm2'].max():.0f} W/m²")
    print(f"   Wind: {df['wind_speed_ms'].min():.1f} to {df['wind_speed_ms'].max():.1f} m/s")
    
    # Check for anomalies
    print(f"\n4. Anomaly Detection:")
    if df['RH_amb_pct'].max() > 100 or df['RH_amb_pct'].min() < 0:
        print("   ✗ RH out of physical range (0-100%)")
    else:
        print("   ✓ RH within valid range")
    
    if df['GHI_Wm2'].max() > 1400:
        print("   ⚠ GHI unusually high (>1400 W/m²)")
    else:
        print("   ✓ GHI within reasonable range")
    
    # Missing data
    print(f"\n5. Missing Data:")
    total_missing = df.isna().sum().sum()
    if total_missing == 0:
        print("   ✓ No missing values")
    else:
        print(f"   ⚠ {total_missing} missing values found:")
        for col in df.columns:
            n_missing = df[col].isna().sum()
            if n_missing > 0:
                print(f"      {col}: {n_missing}")
    
    # Create diagnostic plots
    fig, axes = plt.subplots(4, 1, figsize=(12, 10))
    fig.suptitle(f'Weather Data: {csv_path.stem}', fontsize=14, fontweight='bold')
    
    # Temperature
    axes[0].plot(df['time_index'], df['T_amb_C'], linewidth=0.5)
    axes[0].set_ylabel('Temperature [°C]')
    axes[0].set_title('Ambient Temperature')
    axes[0].grid(True, alpha=0.3)
    
    # RH
    axes[1].plot(df['time_index'], df['RH_amb_pct'], linewidth=0.5, color='blue')
    axes[1].set_ylabel('RH [%]')
    axes[1].set_title('Relative Humidity')
    axes[1].grid(True, alpha=0.3)
    
    # GHI
    axes[2].plot(df['time_index'], df['GHI_Wm2'], linewidth=0.5, color='orange')
    axes[2].set_ylabel('GHI [W/m²]')
    axes[2].set_title('Global Horizontal Irradiance')
    axes[2].grid(True, alpha=0.3)
    
    # Wind
    axes[3].plot(df['time_index'], df['wind_speed_ms'], linewidth=0.5, color='green')
    axes[3].set_ylabel('Wind Speed [m/s]')
    axes[3].set_xlabel('Hour of Year')
    axes[3].set_title('Wind Speed')
    axes[3].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save plot
    plot_path = csv_path.parent / f"{csv_path.stem}_verification.png"
    fig.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"\n✓ Verification plot saved: {plot_path}")
    
    # Monthly statistics
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['month'] = df['datetime'].dt.month
    
    monthly_stats = df.groupby('month').agg({
        'T_amb_C': ['mean', 'min', 'max'],
        'RH_amb_pct': 'mean',
        'GHI_Wm2': 'mean'
    })
    
    print(f"\n6. Monthly Averages:")
    print(monthly_stats.to_string())
    
    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--input',
        type=Path,
        required=True,
        help='Path to standardized weather CSV'
    )
    
    args = parser.parse_args()
    
    verify_weather_data(args.input)
    plt.show()


if __name__ == '__main__':
    main()