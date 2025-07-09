// Enhanced Dispenser with Progress Reporting, Status, and Calibration using AccelStepper
#include <AccelStepper.h>

#define STEP_PIN 9
#define DIR_PIN 8
#define ENABLE_PIN 4    // NEW: Motor driver enable pin
#include <EEPROM.h>


// EEPROM addresses
const int EE_ADDR_SPM = 0;    // float = 4 bytes
const int EE_ADDR_OFFSET = 4; // long  = 4 bytes

void saveCalibration(float spm) {
  EEPROM.put(EE_ADDR_SPM, spm);
}
float loadCalibration() {
  float spm;
  EEPROM.get(EE_ADDR_SPM, spm);
  return spm;
}
void saveOffset(long pos) {
  EEPROM.put(EE_ADDR_OFFSET, pos);
}
long loadOffset() {
  long pos;
  EEPROM.get(EE_ADDR_OFFSET, pos);
  return pos;
}

// Create stepper motor instance
AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

// --- SOFTWARE LIMITS ---
const long MAX_STEPS = 45000*20; // Set based on your hardware: measure full stroke in steps!
const long MIN_STEPS = 0;     // If zero is "fully retracted"


// ========== Calibration Values ==========
const int microstep = 16;
const float full_steps_per_rev = 360.0 / 1.8;        // 200
const float steps_per_rev = full_steps_per_rev * microstep;  // 3200
const float ml_per_rev = 0.5;                      // your syringe calibration
float steps_per_ml = steps_per_rev / ml_per_rev;  // will be ≈6645.23 for ml_per_rev = 0.482

// Driver Enable logic
bool motor_enabled = true;


// --- Calibration variables ---
long calib_start_pos = 0;
long calib_end_pos = 0;
float calib_target_vol = 0;
bool calib_in_progress = false;
bool calib_waiting_for_mass = false;

// Status tracking variables
enum DeviceStatus {
  IDLE,
  DISPENSING,
  CANCELLED,
  ERROR
};

DeviceStatus current_status = IDLE;
bool cancel_requested = false;
float current_volume = 0.0;
float current_rate = 0.0;
float progress_percent = 0.0;
unsigned long last_status_update = 0;
const unsigned long STATUS_UPDATE_INTERVAL = 50; // Update every 50ms for smoother updates


// Detect a jam if you haven’t reached your target after a reasonable time:
const unsigned long MOVE_TIMEOUT = 30000; // 30 s max per move
unsigned long moveStartTime = 0;

// Dispensing variables
long target_position = 0;
long start_position = 0;
unsigned long dispense_start_time = 0;
float dispensed_volume = 0.0;

// ----------------Improve stepper heating-----------------
void set_motor_enabled(bool enabled) {
  motor_enabled = enabled;
  digitalWrite(ENABLE_PIN, enabled ? LOW : HIGH); // For most drivers: LOW=ON, HIGH=OFF
}

void startMove(long target) {
  moveStartTime = millis();     // reset timeout timer
  stepper.moveTo(target);       // or stepper.move(steps);
}


// ----------------- SETUP -----------------
void setup() {
  pinMode(ENABLE_PIN, OUTPUT);
  pinMode(DIR_PIN,  OUTPUT);
  set_motor_enabled(false); // Motor OFF at boot

  Serial.begin(115200);

  // Stepper configuration
  stepper.setMaxSpeed(200);       // steps/sec (tune for your hardware)
  stepper.setAcceleration(100);    // steps/sec^2

  float default_spm = steps_per_rev / ml_per_rev;

    // load what’s in EEPROM
  float stored_spm = loadCalibration();
    // if invalid (<1 or huge), overwrite it with default
    if (!(stored_spm > 0 && stored_spm < 20000)) {
      stored_spm = default_spm;
      saveCalibration(stored_spm);
    }
  steps_per_ml = stored_spm;    
  stepper.setCurrentPosition(loadOffset());
  

  //stepper.setCurrentPosition(0);   // Always zero on power-up
  
  // Startup status
  send_status();
  Serial.println("Ready for DISPENSE:<vol_ml>,<rate_ml_per_min> or CANCEL or STATUS");
  Serial.print("MICROSTEPPING MODE: 1/"); Serial.println(microstep);
  Serial.print("steps_per_rev = "); Serial.println(steps_per_rev);
}

// ----------------- LOOP -----------------
void loop() {
  // --- Handle Serial commands ---
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    Serial.print("[COMMAND RECEIVED] >"); Serial.print(command); Serial.println("<"); // Adding this for debugging

    if (command.startsWith("DISPENSE:")) {
      handle_dispense_command(command);
    } else if (command == "CANCEL") {
      handle_cancel_command();
    } else if (command == "STATUS") {
      send_status();
    } else if (command == "TEST") {
      Serial.println("TEST COMMAND: Move exactly 3 full revolutions");

      long steps_to_move = 3 * steps_per_rev;    // This is 9600 for 1/16 microstep
      Serial.print("steps_per_rev = "); Serial.println(steps_per_rev);
      Serial.print("steps_to_move = "); Serial.println(steps_to_move);

      start_position = stepper.currentPosition();
      target_position = start_position + steps_to_move;
      Serial.print("start_position = "); Serial.println(start_position);
      Serial.print("target_position = "); Serial.println(target_position);

      set_motor_enabled(true);
      startMove(target_position);

      current_status = DISPENSING;
    }


    else if (command.indexOf("RAPID_DISPENSE:") == 0) {
      handle_rapid_dispense_command(command);
    }
    // What if we don't start with a full syringe?
    else if (command.startsWith("SET_VOL:")) {
      float vol = command.substring(8).toFloat();     // user sends mL remaining
      long steps = vol * steps_per_ml;
      stepper.setCurrentPosition(steps);               // now position matches real plunger
      Serial.print("Offset set: "); Serial.print(vol); Serial.println(" mL");
      saveOffset(stepper.currentPosition());
    }

    else if (command == "RETRACT") {
      long pos = stepper.currentPosition();
      if (pos != 0) {
        startMove(0);
        while (stepper.distanceToGo() != 0) { stepper.run(); }
      }
      set_motor_enabled(false);
      Serial.println("RETRACT_COMPLETE");
      
    }

    else if (command.startsWith("SET_POS:")) {
      long p = command.substring(8).toInt();
      stepper.setCurrentPosition(p);
      Serial.print("Position set to "); Serial.println(p);
      saveOffset(stepper.currentPosition());  // ← persist the new zero offset
    }

    else if (command.startsWith("CALIBRATE:")) {
      handle_calibrate_command(command);
    }
    else if (command.startsWith("ACTUAL_MASS:")) {
      handle_actual_mass_command(command);
    }




    // room for more states
  }

  // --- Stepper runs always ---
  stepper.run();

  // --- Dispense logic ---
  if (current_status == DISPENSING) {
    // Progress tracking
    long total_distance = target_position - start_position;
    long current_pos = stepper.currentPosition();
    
    if (total_distance > 0) {
      progress_percent = ((float)(current_pos - start_position) / (float)total_distance) * 100.0;
      if (progress_percent > 100.0) progress_percent = 100.0;
      dispensed_volume = current_volume * (progress_percent / 100.0);
    }

    if (cancel_requested) {
    stepper.stop();
    stepper.setCurrentPosition(stepper.currentPosition());
    current_status = CANCELLED;
    Serial.println("DISPENSE_CANCELLED");
    progress_percent = 0.0;
    dispensed_volume = 0.0;
    send_status();
    set_motor_enabled(false); // help with heating issue
    return;
}


    // Check for completion
    if (stepper.distanceToGo() == 0) {
      current_status = IDLE;
      Serial.println("DISPENSE_COMPLETE");
      progress_percent = 100.0;
      dispensed_volume = current_volume;
      send_status();
      set_motor_enabled(false);
    }

    // Send progress every STATUS_UPDATE_INTERVAL
    if ((millis() - last_status_update) >= STATUS_UPDATE_INTERVAL) {
      send_progress_update();
      last_status_update = millis();
    }
  }
}



// --- RAPID DISPENSE ---
void handle_rapid_dispense_command(String command) {
  if (current_status == DISPENSING) {
    Serial.println("ERROR: Already dispensing. Send CANCEL first.");
    return;
  }
  int colonIndex = command.indexOf(':');
  if (colonIndex > 0) {
    float volume = command.substring(colonIndex + 1).toFloat();
    Serial.print("[DEBUG] Parsed rapid dispense volume: "); Serial.println(volume, 3);

    if (volume <= 0) {
      Serial.println("ERROR: Volume must be positive.");
      current_status = ERROR;
      send_status();
      return;
    }

    current_volume = volume;
    current_rate = 1000.0; // Highest safe speed (ml/min)
    current_status = DISPENSING;
    cancel_requested = false;
    progress_percent = 0.0;
    dispensed_volume = 0.0;
    dispense_start_time = millis();

    Serial.print("RAPID_DISPERSE_START: ");
    Serial.print(volume, 2);
    Serial.println(" mL");

    long steps_to_move = volume * steps_per_ml;
    Serial.print("[DEBUG] steps_per_ml: "); Serial.println(steps_per_ml, 3);
    Serial.print("[DEBUG] steps_to_move: "); Serial.println(steps_to_move);

    start_position = stepper.currentPosition();
    long next_target = start_position + steps_to_move;
    if (next_target > MAX_STEPS) next_target = MAX_STEPS;
    if (next_target < MIN_STEPS) next_target = MIN_STEPS;
    target_position = next_target;

    Serial.print("[DEBUG] start_position: "); Serial.println(start_position);
    Serial.print("[DEBUG] next_target: "); Serial.println(next_target);

    float max_speed = 2000; // steps/sec (adjust as needed)
    float max_accel = 4000; // steps/sec^2
    stepper.setMaxSpeed(max_speed);
    stepper.setAcceleration(max_accel);
    set_motor_enabled(true);
    startMove(next_target); 
    

    Serial.print("[DEBUG] stepper max speed: "); Serial.println(max_speed);
    Serial.print("[DEBUG] stepper accel: "); Serial.println(max_accel);
    Serial.print("[DEBUG] current_status: "); Serial.println(current_status == DISPENSING ? "DISPENSING" : "NOT DISPENSING");

    send_status();
  } else {
    Serial.println("ERROR: Invalid RAPID_DISPERSE format. Use RAPID_DISPERSE:<vol_ml>");
    current_status = ERROR;
    send_status();
  }
}



// --- DISPENSE ---
void handle_dispense_command(String command) {
  if (current_status == DISPENSING) {
    Serial.println("ERROR: Already dispensing. Send CANCEL first.");
    return;
  }

  int commaIndex = command.indexOf(',');
  if (commaIndex > 9) {
    float volume = command.substring(9, commaIndex).toFloat();
    float rate = command.substring(commaIndex + 1).toFloat();

    if (volume <= 0 || rate <= 0) {
      Serial.println("ERROR: Volume and rate must be positive");
      current_status = ERROR;
      send_status();
      return;
    }

    current_volume = volume;
    current_rate = rate;
    current_status = DISPENSING;
    cancel_requested = false;
    progress_percent = 0.0;
    dispensed_volume = 0.0;
    dispense_start_time = millis();

    // Calculate before using!
    long steps_to_move = volume * steps_per_ml;
    float speed_steps_per_sec = (rate / 60.0) * steps_per_ml;
    stepper.setMaxSpeed(speed_steps_per_sec);           // use user’s rate!
    stepper.setAcceleration(speed_steps_per_sec * 2);   // or tune as desired
    set_motor_enabled(true);              // enable first

    // Debug prints (NOW the variables are defined!)
    Serial.print("steps_to_move = "); Serial.println(steps_to_move);
    Serial.print("speed_steps_per_sec = "); Serial.println(speed_steps_per_sec, 3);

    // Clamp to max steps allowed
    start_position = stepper.currentPosition();
    long next_target = start_position + steps_to_move;
    if (next_target > MAX_STEPS) next_target = MAX_STEPS;
    if (next_target < MIN_STEPS) next_target = MIN_STEPS;
    target_position = next_target;
    startMove(next_target);


    send_status();

  } else {
    Serial.println("ERROR: Invalid DISPENSE format. Use DISPENSE:volume,rate");
    current_status = ERROR;
    send_status();
  }
}




// --- CANCEL ---
void handle_cancel_command() {
  if (current_status == DISPENSING) {
    cancel_requested = true;
    Serial.println("CANCEL_REQUESTED");
  } else {
    Serial.println("INFO: No active dispensing to cancel");
  }
}

// --- Simple status/progress output ---
void send_status() {
  Serial.print("STATUS: ");
  switch (current_status) {
    case IDLE:
      Serial.println("IDLE");
      break;
    case DISPENSING:
      Serial.print("DISPENSING - ");
      Serial.print(current_volume);
      Serial.print("mL @ ");
      Serial.print(current_rate);
      Serial.print("mL/min - ");
      Serial.print(progress_percent, 1);
      Serial.println("%");
      break;
    case CANCELLED:
      Serial.println("CANCELLED");
      break;
    case ERROR:
      Serial.println("ERROR");
      break;
  }
}

// --- PROGRESS/DETAILS ---
void send_comprehensive_update() {
  unsigned long elapsed_time = millis() - dispense_start_time;
  float elapsed_minutes = elapsed_time / 60000.0;
  float remaining_volume = current_volume - dispensed_volume;
  float estimated_remaining_time = 0;
  
  if (current_rate > 0) {
    estimated_remaining_time = remaining_volume / current_rate; // in minutes
  }
  
  float current_speed = stepper.speed(); // steps per second
  float current_speed_ml_min = (current_speed / steps_per_ml) * 60.0;

  Serial.print("PROGRESS_DETAILED: ");
  Serial.print(progress_percent, 1);
  Serial.print("%,");
  Serial.print(dispensed_volume, 2);
  Serial.print("mL,");
  Serial.print(remaining_volume, 2);
  Serial.print("mL,");
  Serial.print(elapsed_minutes, 1);
  Serial.print("min,");
  Serial.print(estimated_remaining_time, 1);
  Serial.print("min,");
  Serial.print(current_speed_ml_min, 1);
  Serial.print("mL/min,");
  Serial.print(stepper.currentPosition());
  Serial.print("steps,");
  Serial.print(stepper.distanceToGo());
  Serial.println("steps_remaining");

  send_progress_update();
}

void send_progress_update() {
  Serial.print("PROGRESS: ");
  Serial.print(progress_percent, 1);
  Serial.print("% - ");
  Serial.print(dispensed_volume, 2);
  Serial.print("/");
  Serial.print(current_volume);
  Serial.println("mL");
}



// --- CALIBRATION HANDLERS ---
void handle_calibrate_command(String command) {
  if (calib_in_progress) {
    Serial.println("ERROR: Calibration already in progress!");
    return;
  }

  int colonIndex = command.indexOf(':');
  if (colonIndex <= 0) {
    Serial.println("ERROR: Invalid CALIBRATE format. Use CALIBRATE:<vol_ml>");
    return;
  }

  // 1) Parse and validate volume
  calib_target_vol = command.substring(colonIndex + 1).toFloat();
  if (calib_target_vol <= 0) {
    Serial.println("ERROR: Calibration volume must be positive");
    return;
  }

  // 2) Notify user
  Serial.print("CALIBRATION: Dispensing ");
  Serial.print(calib_target_vol, 3);
  Serial.println(" mL. Please prepare your scale.");

  // 3) Mark calibration in progress
  calib_in_progress      = true;
  calib_waiting_for_mass = true;
  calib_start_pos        = stepper.currentPosition();

  // 4) Compute target position
  long steps_to_move = calib_target_vol * steps_per_ml;
  long next_target   = calib_start_pos + steps_to_move;
  next_target = constrain(next_target, MIN_STEPS, MAX_STEPS);
  target_position = next_target;

  // 5) Configure a safe, steady calibration speed
  const float CALIB_FULL_SPEED = 50.0;                 // 50 full-steps/sec
  const float CALIB_SPEED      = CALIB_FULL_SPEED * microstep;  // in microsteps/sec
  stepper.setMaxSpeed(CALIB_SPEED);
  stepper.setAcceleration(CALIB_SPEED * 2);           // ramp at 2× speed

  // 6) Enable driver and start move (with timeout)
  set_motor_enabled(true);
  moveStartTime     = millis();
  stepper.moveTo(next_target);

  // 7) Initialize dispense-tracking state
  current_status         = DISPENSING;
  cancel_requested       = false;
  progress_percent       = 0.0;
  dispensed_volume       = 0.0;
  dispense_start_time    = millis();

  // 8) Would be nice to send out a status as soon as we start
  send_status();
}


void handle_actual_mass_command(String command) {
  if (!calib_in_progress || !calib_waiting_for_mass) {
    Serial.println("ERROR: No calibration awaiting mass input.");
    return;
  }
  int colonIndex = command.indexOf(':');
  if (colonIndex > 0) {
    float actual_grams = command.substring(colonIndex + 1).toFloat();
    if (actual_grams <= 0) {
      Serial.println("ERROR: Mass must be positive.");
      return;
    }
    calib_end_pos = stepper.currentPosition();
    long steps_moved = abs(calib_end_pos - calib_start_pos);
    float new_steps_per_ml = steps_moved / actual_grams; // 1g = 1mL for water

    Serial.print("Measured steps moved: "); Serial.println(steps_moved);
    Serial.print("Measured actual mass (g): "); Serial.println(actual_grams, 3);

    Serial.print("CALIBRATION COMPLETE: steps_per_ml = ");
    Serial.println(new_steps_per_ml, 5);
    Serial.println("You can now update steps_per_ml in your code.");
    saveCalibration(new_steps_per_ml);
    saveOffset(stepper.currentPosition());
    calib_in_progress = false;
    calib_waiting_for_mass = false;
    current_status = IDLE;         // (optional)
    set_motor_enabled(false);      // (optional)
  } else {
    Serial.println("ERROR: Invalid ACTUAL_MASS format. Use ACTUAL_MASS:<grams>");
  }
}

