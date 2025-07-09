// Non Accel-Stepper library test run for 3 revolutions

#define STEP_PIN 9
#define DIR_PIN 8
#define ENABLE_PIN 10


const int microsteps = 16;
const int full_steps_per_rev = 360 / 1.8; // 200
const int steps_per_rev = full_steps_per_rev * microsteps; // 3200
const int total_revs = 3;
const int total_steps = steps_per_rev * total_revs; // 9600

const int step_delay_us = 1000; // adjust if needed

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENABLE_PIN, OUTPUT);

  digitalWrite(ENABLE_PIN, LOW); // Enable motor driver
  digitalWrite(DIR_PIN, HIGH);   // Set direction (change if needed)

  Serial.begin(115200);
  Serial.println("Starting 3 full revolutions at 1/16 microstepping...");

  for (long i = 0; i < total_steps; i++) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(step_delay_us);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(step_delay_us);

    if (i % 1000 == 0) {
      Serial.print("Step: ");
      Serial.println(i);
    }
  }

  digitalWrite(ENABLE_PIN, HIGH); // Disable motor driver
  Serial.println("Done! 3 revolutions complete.");
}

void loop() {}
