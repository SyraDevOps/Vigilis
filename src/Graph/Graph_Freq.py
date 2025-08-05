import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import os
import numpy as np

# Set style for better visualization
plt.style.use('seaborn-v0_8')
sns.set_theme(style="whitegrid")

def load_and_prepare_data():
    """Load and prepare the data for visualization."""
    # Read the CSV file with proper path
    df = pd.read_csv('./detections.csv')
    
    # Convert frequencies string to list of floats, handling both string and float inputs
    def parse_frequencies(freq_str):
        if pd.isna(freq_str):
            return []
        if isinstance(freq_str, (int, float)):
            return [float(freq_str)]
        return [float(f.strip()) for f in freq_str.split(';') if f.strip()]
        
    df['freq_list'] = df['frequencies'].apply(parse_frequencies)
    
    # Clean time format (replace : with .)
    df['time'] = df['time'].str.replace(':', '.')
    
    # Convert date and time to datetime, handling different formats
    def parse_datetime(row):
        try:
            return pd.to_datetime(f"{row['date']} {row['time']}", 
                                format='%y.%m.%d %H.%M')
        except:
            try:
                return pd.to_datetime(f"{row['date']} {row['time']}", 
                                    format='%y.%m.%d %H:%M')
            except:
                return pd.NaT
    
    df['datetime'] = df.apply(parse_datetime, axis=1)
    
    # Remove any rows where datetime parsing failed or no frequencies
    df = df.dropna(subset=['datetime'])
    df = df[df['freq_list'].apply(len) > 0]
    
    # Sort by datetime
    df = df.sort_values('datetime')
    
    return df

def create_frequency_time_plot(df):
    """Create an enhanced scatter plot of frequencies over time."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Get unique timestamps for color mapping
    unique_times = df['datetime'].unique()
    colors = sns.color_palette("husl", n_colors=len(unique_times))
    time_to_color = dict(zip(unique_times, colors))
    
    # Create scatter plot with enhanced styling
    for idx, row in df.iterrows():
        for freq in row['freq_list']:
            ax.scatter(row['datetime'], freq, 
                      alpha=0.7, 
                      s=100,
                      color=time_to_color[row['datetime']],
                      edgecolor='white',
                      linewidth=0.5)
    
    # Enhance the plot styling
    ax.set_title('Meteor Detection Frequencies Over Time', 
                 fontsize=16, 
                 pad=20,
                 fontweight='bold')
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Frequency (kHz)', fontsize=12)
    
    # Format x-axis
    plt.xticks(rotation=45, ha='right')
    
    # Add grid with custom styling
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Add a light background color
    ax.set_facecolor('#f0f0f0')
    
    plt.tight_layout()
    return plt

def create_frequency_histogram(df):
    """Create an enhanced histogram of frequency distributions."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Flatten list of frequencies
    all_frequencies = [freq for freq_list in df['freq_list'] for freq in freq_list]
    
    # Create histogram with enhanced styling
    sns.histplot(data=all_frequencies,
                bins=15,
                color='skyblue',
                edgecolor='black',
                alpha=0.7,
                ax=ax)
    
    ax.set_title('Distribution of Detected Frequencies', 
                 fontsize=16, 
                 pad=20,
                 fontweight='bold')
    ax.set_xlabel('Frequency (kHz)', fontsize=12)
    ax.set_ylabel('Number of Detections', fontsize=12)
    
    # Add mean and median lines
    mean_freq = np.mean(all_frequencies)
    median_freq = np.median(all_frequencies)
    
    ax.axvline(mean_freq, color='red', linestyle='--', alpha=0.8, label=f'Mean: {mean_freq:.2f} kHz')
    ax.axvline(median_freq, color='green', linestyle='--', alpha=0.8, label=f'Median: {median_freq:.2f} kHz')
    
    ax.legend()
    plt.tight_layout()
    
    return plt

def create_frequency_analysis():
    """Create and save the frequency analysis visualizations."""
    # Ensure the graphs directory exists
    os.makedirs('./../graphs', exist_ok=True)
    
    try:
        # Load and prepare data
        df = load_and_prepare_data()
        
        if len(df) == 0:
            print("No valid data found to analyze")
            return
            
        # Create time series plot
        time_plot = create_frequency_time_plot(df)
        # Save plot
        time_plot.savefig('./../graphs/frequency_over_time.png', 
                         dpi=300, 
                         bbox_inches='tight',
                         facecolor='white')
        
        # Create histogram
        hist_plot = create_frequency_histogram(df)
        # Save plot
        hist_plot.savefig('./../graphs/frequency_distribution.png', 
                         dpi=300, 
                         bbox_inches='tight',
                         facecolor='white')
        
        # Print summary statistics
        all_freqs = [freq for freq_list in df['freq_list'] for freq in freq_list]
        print("\n=== Frequency Analysis Summary ===")
        print(f"Total number of detections: {len(all_freqs)}")
        print(f"Most common frequency: {max(set(all_freqs), key=all_freqs.count):.2f} kHz")
        print(f"Average frequency: {np.mean(all_freqs):.2f} kHz")
        print(f"Median frequency: {np.median(all_freqs):.2f} kHz")
        print(f"Frequency range: {min(all_freqs):.2f} - {max(all_freqs):.2f} kHz")
        
        # Display both plots
        plt.show()
        
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        raise  # Re-raise for debugging

if __name__ == "__main__":
    create_frequency_analysis()