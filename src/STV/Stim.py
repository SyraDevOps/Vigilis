import pandas as pd
import numpy as np
from datetime import datetime
import os

def estimate_height(frequency_khz):
    """Estimate meteor height based on frequency."""
    # Convert kHz to MHz for calculations
    frequency_mhz = frequency_khz / 1000
    
    if frequency_mhz < 30:
        return (None, "Frequência muito baixa para meteor scatter")
    elif 30 <= frequency_mhz <= 60:
        return (100, "90-110 km")  # média de 100km
    elif 60 < frequency_mhz <= 100:
        return (100, "95-105 km")
    elif 100 < frequency_mhz <= 150:
        return (100, "100 km (trilhas densas)")
    else:
        return (None, "Frequência muito alta para meteor scatter")

def calculate_plasma_frequency(frequency_khz):
    """Calculate plasma frequency and electron density."""
    f_mhz = frequency_khz / 1000
    Ne = (f_mhz / 8.98) ** 2
    return Ne

def analyze_meteor_data(df):
    """Analyze meteor data and add calculated fields."""
    results = []
    
    for idx, row in df.iterrows():
        for freq in row['freq_list']:
            # Basic data
            result = {
                'datetime': row['datetime'],
                'frequency_khz': freq,
                'frequency_mhz': freq / 1000,
                'observer': row['observer'],
                'location': row['location'],
                'receiver': row['receiver'],
                'antenna': row['antenna']
            }
            
            # Calculate height estimate
            height, height_range = estimate_height(freq)
            result['estimated_height_km'] = height
            result['height_range'] = height_range
            
            # Calculate plasma parameters
            result['electron_density'] = calculate_plasma_frequency(freq)
            
            # Calculate wavelength
            result['wavelength_m'] = 299792458 / (freq * 1000)  # c/f
            
            results.append(result)
    
    return pd.DataFrame(results)

def create_detailed_analysis():
    """Create detailed analysis and save to CSV."""
    try:
        # Load original data
        df = pd.read_csv('./detections.csv')
        
        # Convert frequencies string to list of floats, handling both string and float inputs
        def parse_frequencies(freq_str):
            if pd.isna(freq_str):
                return []
            if isinstance(freq_str, (int, float)):
                return [float(freq_str)]
            return [float(f.strip()) for f in freq_str.split(';') if f.strip()]
            
        df['freq_list'] = df['frequencies'].apply(parse_frequencies)
        
        # Clean and standardize time format before parsing
        df['time'] = df['time'].str.replace(':', '.')
        
        # Convert date and time to datetime, handling different formats
        def parse_datetime(row):
            try:
                return pd.to_datetime(f"{row['date']} {row['time']}", 
                                    format='%y.%m.%d %H.%M')
            except:
                try:
                    # Try alternative format if first attempt fails
                    return pd.to_datetime(f"{row['date']} {row['time']}", 
                                        format='%y.%m.%d %H:%M')
                except:
                    return pd.NaT
        
        df['datetime'] = df.apply(parse_datetime, axis=1)
        
        # Remove any rows where datetime parsing failed or no frequencies
        df = df.dropna(subset=['datetime'])
        df = df[df['freq_list'].apply(len) > 0]
        
        # Analyze data
        detailed_df = analyze_meteor_data(df)
        
        # Save results
        output_file = './analysis/meteor_analysis.csv'
        os.makedirs('./analysis', exist_ok=True)
        detailed_df.to_csv(output_file, index=False)
        
        # Print summary
        print("\n=== Meteor Analysis Summary ===")
        print(f"Total detections analyzed: {len(detailed_df)}")
        if len(detailed_df) > 0:
            print(f"Average estimated height: {detailed_df['estimated_height_km'].mean():.2f} km")
            print(f"Average electron density: {detailed_df['electron_density'].mean():.2e} electrons/cm³")
            print(f"Wavelength range: {detailed_df['wavelength_m'].min():.2f} - {detailed_df['wavelength_m'].max():.2f} m")
        print(f"\nResults saved to: {output_file}")
        
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        raise  # Re-raise the exception for debugging

if __name__ == "__main__":
    create_detailed_analysis()