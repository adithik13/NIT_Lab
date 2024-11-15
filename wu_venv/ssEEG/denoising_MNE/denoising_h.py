import matplotlib.pyplot as plt
import pandas as pd
from scipy import signal
from scipy.signal import butter, filtfilt, iirnotch, detrend
import numpy as np
import pywt
import mne
from mne.preprocessing import ICA
import os
from mne.time_frequency import tfr_multitaper

class DataPreprocess:
    # in order to use the .csv file with mne, we need to first 
    # convert it to a fif file format 
    def remove_missing(csv_path):
        df = pd.read_csv(csv_path, skiprows=11, engine='python')
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=['Volt'])
        eeg_data = df['Volt'].values
        expected_samples = 1400000
        
        if len(eeg_data) != expected_samples:
            raise ValueError(f"Expected {expected_samples} samples, but got {len(eeg_data)} samples.")
        
        return eeg_data
        
    def convert_to_fif(eeg_data):
        try:
            sfreq = 5000
            info = mne.create_info(ch_names=['EEG'], sfreq=sfreq, ch_types=['eeg'])
            #eeg_data = eeg_data / 1000.0
            eeg_data = eeg_data.reshape(1,-1)
            raw = mne.io.RawArray(eeg_data, info)

            fif_path = "eeg_data_raw.fif"
            raw.save(fif_path, overwrite=True)
            message =  f"CSV converted to FIF and saved at {fif_path}"
            return raw, message
        
        except Exception as e:
            return f"Error occurred: {e}"
        
        
class Filter:
    
    def inspect_signal(raw):
        data = raw.get_data()
        min_value = np.min(data)
        max_value = np.max(data)
        mean_value = np.mean(data)
        std_dev = np.std(data)
        print(f"Signal Statistics - Min: {min_value:.2f}, Max: {max_value:.2f}, Mean: {mean_value:.2f}, Std Dev: {std_dev:.2f}")

    @staticmethod
    def apply_downsampling(raw, new_sfreq=5000):
        # Downsample the data
        raw.resample(new_sfreq, npad="auto")
        print(f"Data downsampled to {new_sfreq} Hz.")
        return raw

    @staticmethod
    def apply_detrend(raw):
        data = raw.get_data()
        data = mne.filter.detrend(data, order=1)
        raw._data = data
        return raw
    
    def apply_bandpass_filter(raw):
        raw.filter(l_freq=0.5, h_freq=30, picks='eeg')
        return raw
    
    @staticmethod
    def apply_notch_filter(raw):
        raw.notch_filter(freqs=[50, 60], picks='eeg')
        return raw

    @staticmethod
    def apply_all_filters(raw):
        raw = Filter.apply_detrend(raw)
        raw = Filter.apply_notch_filter(raw)
        raw = Filter.apply_bandpass_filter(raw)
        return raw
    
    def average_signal(raw):
        data = raw.get_data()

        avg_data = np.mean(data, axis=0)

        print(f"Averaged signal computed. Length: {len(avg_data)} samples.")
        return avg_data
    
    @staticmethod
    def average_filtered(filtered_raw):
        averaged_signal = Filter.average_signal(filtered_raw)

        plt.figure(figsize=(10, 4))
        plt.plot(averaged_signal, label='Averaged EEG Signal')
        plt.xlabel('Sample Index')
        plt.ylabel('Voltage (V)')
        plt.title('Averaged EEG Signal')
        plt.grid()
        plt.legend()
        plt.show()


class Plot:
    @staticmethod
    def plot_original(eeg_data):
        plt.plot(eeg_data[:10000])  # teh first (~2 seconds)
        plt.xlabel("Sample Index")
        plt.ylabel("Voltage (V)")
        plt.title("Subset of Raw EEG Signal from .csv")
        plt.savefig("wu_venv/ssEEG/denoising_MNE/output/original_eeg_plot.png", dpi=300)
        plt.close()

    @staticmethod
    def plot_raw(raw):
        fig = raw.plot(scalings='auto', n_channels=1, duration=40, title="Raw EEG Signal", show=False)
        fig.savefig("wu_venv/ssEEG/denoising_MNE/output/raw_eeg_plot.png", dpi=300)
        plt.close(fig)

    @staticmethod
    def plot_filtered_raw(filtered_raw):
        fig = filtered_raw.plot(scalings='auto', n_channels=1, duration=40, title="Filtered EEG Signal", show=False)
        fig.savefig("wu_venv/ssEEG/denoising_MNE/output/filtered_eeg_plot.png", dpi=300)
        plt.close(fig)

    @staticmethod
    def plot_cropped_event_segment(raw, event_name, start_time, end_time):
        start_time = max(0, start_time)
        end_time = min(raw.times[-1], end_time)
        
        duration = end_time - start_time
        
        data = raw.get_data()
        std_dev = np.std(data)
        dynamic_scaling = std_dev * 2
        custom_scalings = {'eeg': dynamic_scaling}
        
        print(f"Using dynamic scaling: {dynamic_scaling:.2e}")
        print(f"Cropping and plotting {event_name} from {start_time}s to {end_time}s")

        # crop
        cropped_raw = raw.copy().crop(tmin=start_time, tmax=end_time)

        fig = cropped_raw.plot(
            scalings=custom_scalings,
            n_channels=1,
            duration=duration,
            title=f"EEG Signal: {event_name} (Cropped)",
            show=False
        )

        save_path = f"wu_venv/ssEEG/denoising_MNE/output/{event_name.lower().replace(' ', '_')}_cropped_segment.png"
        fig.savefig(save_path, dpi=300)
        plt.close(fig)
        print(f"Saved cropped plot for {event_name} at {save_path}")

    @staticmethod
    def plot_event_segment(raw, event_name, start_time, end_time):
        data = raw.get_data()
        std_dev = np.std(data)
        
        dynamic_scaling = std_dev * 2  
        custom_scalings = {'eeg': dynamic_scaling}
        print(f"Using dynamic scaling: {dynamic_scaling:.2e}")

        duration = end_time - start_time
        fig = raw.plot(
            start=start_time,
            duration=duration,
            scalings=custom_scalings,
            n_channels=1,
            title=f"EEG Signal: {event_name}",
            show=False
        )
        
        save_path = f"wu_venv/ssEEG/denoising_MNE/output/{event_name.lower().replace(' ', '_')}_segment.png"
        fig.savefig(save_path, dpi=300)
        plt.close(fig)
        print(f"Saved plot for {event_name} at {save_path}")

class Events:
    @staticmethod
    def get_events_dict():
        return {
            "Sound On": (0, 40),          # From 0s to 40s in EEG time
            "Sound Off": (40, 113),       # From 40s to 113s
            "Touch Whiskers": (113, 173), # From 113s to 173s
            "Stop Touching": (173, 280),  # From 173s to 280s
        }
    
    
class FFT:
    def compute_psd_plot(raw):
        fig = psd = raw.compute_psd(method='welch', fmin=0.5, fmax=50, n_fft=2048, n_overlap=512)
        psd.plot()
        plt.show()
        plt.figure()
        psd.plot(dB=True)
        plt.savefig("wu_venv/ssEEG/denoising_MNE/output/mne_psd_line_plot.png", dpi=300)
        plt.close()

    def compute_tfr_multitaper(raw):
        try:
            print("Performing Time-Frequency Analysis using Multitaper method...")
            
            epochs = mne.make_fixed_length_epochs(raw, duration=3.0, overlap=1.0)
            
            power = epochs.compute_tfr(
                method="multitaper", freqs=np.linspace(0.5, 40, 100), n_cycles=1.5, time_bandwidth=2.0, return_itc=False
            )
            
            power_avg = power.average()
            
            fig = power_avg.plot(baseline=(None, 0), mode='logratio', title='Averaged TFR Multitaper')
            plt.show()
            save_path = f"wu_venv/ssEEG/denoising_MNE/output/tfr_multitaper_color_plot.png"
            #fig.savefig(save_path, dpi=300)
            #plt.close(fig)
            print("TFR analysis and averaged plotting completed.")
            
        except Exception as e:
            print(f"An error occurred while performing TFR analysis: {e}")
