<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This design is a simple SPI-controlled PWM generator running from a 10 MHz system clock. It consists of two main submodules:

1. **SPI Peripheral**  
   - **Pins:**  
     - `SCLK` (ui[0]) – SPI clock  
     - `COPI` (ui[1]) – Controller-out, Peripheral-in data  
     - `nCS`  (ui[2]) – Active-low chip select  
   - **Operation:**  
     - On the falling edge of `nCS`, the peripheral begins shifting in a 16-bit command word, sampling `COPI` on each rising edge of `SCLK`.  
     - Once all 16 bits are received, the first 4 bits select one of the 16 PWM channels (0–15), and the next 8 bits set that channel’s duty cycle (0–255).  
     - Any remaining bits may be reserved for future control flags.  
     - The received duty value is then written into the corresponding register in the PWM block.

2. **PWM Peripheral**  
   - **Clock:** 10 MHz system clock  
   - **Channels:**  
     - 8 “output” channels on `uo[0]`…`uo[7]`  
     - 8 “bidirectional” channels on `uio[0]`…`uio[7]` (used here as additional outputs)  
   - **Operation:**  
     - A free-running 8-bit counter increments on each system clock tick.  
     - For each channel, its duty register (0–255) is compared against the counter:  
       - If `counter < duty`, the output is driven high.  
       - Otherwise, the output is driven low.  
     - This generates an 8-bit (0–100%) PWM signal on each pin.

By combining these two blocks, you can reconfigure any of the 16 PWM outputs on the fly simply by sending a new 16-bit frame over SPI.  

