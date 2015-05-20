#--------------------------------------------------------
#   pisciweb : petite interface avec ma piscine.
#--------------------------------------------------------
from flask import Flask, url_for, render_template, redirect
import glob
import time
import datetime
import os
import RPi.GPIO as gpio
import argparse
import sys

app = Flask(__name__)

#--------------------------------------------------------
# Generalites
#--------------------------------------------------------
pisciWebVersion = "1.3"   # introduction de la gestion des arguments
#pisciWebVersion = "1.2"  # Ajout d'un mode debug
#pisciWebVersion = "1.1"  # Ajout d'une desactivation
#pisciWebVersion = "1.0"  # Premiere version operationnelle

logFileName = "/home/pi/pisciweb/raspiscine.log"

sondeTemperatureEau = "28-0000037ae572"
sondeTemperatureLocal = "28-0000037b14c5"

#--------------------------------------------------------
# Logage d'un message
#--------------------------------------------------------
def log(message):
   logFile=open(logFileName, "a");
   logFile.write("["+time.asctime( time.localtime(time.time()) ) + "] " + message + "\n");
   logFile.close()
   
#--------------------------------------------------------
# Les sondes thermiques WARNING : hardcode  pas beau
#--------------------------------------------------------
base_dir = '/sys/bus/w1/devices/'
#device_folder = glob.glob(base_dir + '28*')[0]
device_folder = base_dir + sondeTemperatureEau
device_file = device_folder + '/w1_slave'

#--------------------------------------------------------
# Le gpio
#--------------------------------------------------------

# Les pins utilisees
pinActive = 11
pinPompe = 12
pinControlepH = 13

# Quelques "macros"
gpioMarche = gpio.HIGH
gpioArret = gpio.LOW

gpioPins = {
   pinActive : {
      'nom'  : 'Activation',
      'etat' : gpioMarche
   },   
   pinPompe : {
      'nom'  : 'Filtration',
      'etat' : gpioArret
   },   
   pinControlepH : {
      'nom' : 'Controle pH',
      'etat' : gpioArret
   }
}

#========================================================
# Gestion du gpio
#========================================================
#--------------------------------------------------------
# Initialisation du systeme
#    w : Activation des warnings ?
#--------------------------------------------------------
def gpioInit(w=True):
   gpio.setwarnings(w) 
   gpio.setmode(gpio.BOARD)
   for pin in gpioPins:
      gpio.setup(pin, gpio.OUT)
   
#--------------------------------------------------------
# Lecture de l'etat des commandes
#--------------------------------------------------------
def lireEtatCommandes():
   for pin in gpioPins:
      gpioPins[pin]['etat'] = gpio.input(pin)

#--------------------------------------------------------
# Lecture de la temperature d'une sonde
#--------------------------------------------------------
def read_temp_raw():
   f = open(device_file, 'r')
   lines = f.readlines()
   f.close()
   return lines
 
def read_temp():
   lines = read_temp_raw()
   while lines[0].strip()[-3:] != 'YES':
      time.sleep(0.2)
      lines = read_temp_raw()
   equals_pos = lines[1].find('t=')
   if equals_pos != -1:
      temp_string = lines[1][equals_pos+2:]
      temp_c = float(temp_string) / 1000.0
      return temp_c

#========================================================
# Gestion de l'interface web
#========================================================

#--------------------------------------------------------
# La page de debogage
#--------------------------------------------------------
@app.route("/debogage")
def debogage():
   message = "Etat du systeme"
   # For each pin, read the pin state and store it in the pins dictionary:
   for pin in gpioPins:
      gpioPins[pin]['state'] = gpio.input(pin)

   # Along with the pin dictionary, put the message into the template data dictionary:
   templateData = {
      'message' : message,
      'gpioPins' : gpioPins
   }

   return render_template('debogage.html', **templateData)

@app.route("/<changePin>/<action>")
def action(changePin, action):
   # Convert the pin from the URL into an integer:
   changePin = int(changePin)
   # Get the device name for the pin being changed:
   deviceName = gpioPins[changePin]['nom']
   # If the action part of the URL is "high," execute the code indented below:
   if action == "high":
      # Set the pin high:
      gpio.output(changePin, gpio.HIGH)
      # Save the status message to be passed into the template:
      message = "Turned " + deviceName + " high."
   if action == "low":
      gpio.output(changePin, gpio.LOW)
      message = "Turned " + deviceName + " low."
   if action == "toggle":
      # Read the pin and set it to whatever it isn't (that is, toggle it):
      gpio.output(changePin, not gpio.input(changePin))
      message = "Toggled " + deviceName + "."

   # For each pin, read the pin state and store it in the pins dictionary:
   for pin in gpioPins:
      gpioPins[pin]['etat'] = gpio.input(pin)

   # Along with the pin dictionary, put the message into the template data dictionary:
   templateData = {
      'message' : message,
      'gpioPins' : gpioPins
   }

   return redirect('/debogage')

#--------------------------------------------------------
# La page principale
#--------------------------------------------------------
@app.route("/")
def hello():
   print("Acces a la racine\n")
   lireEtatCommandes()
   print("Commandes lues\n")
   templateData = {
      'title' : 'Bienvenue dans la piscine Chaput !',
      'date' : datetime.date.today().strftime("%a %d %b %y"),
      'activation' : gpioPins[pinActive]['etat'],
      'etatPompe' : gpioPins[pinPompe]['etat'],
      'etatControlepH' : gpioPins[pinControlepH]['etat'],
      'gpioMarche' : gpioMarche,
      'tempEau': read_temp(),
      'pisciWebVersion': pisciWebVersion
   }
   print("Rendu en cours \n")
   return render_template('main.html', **templateData)

#--------------------------------------------------------
# Mise en marche de la pompe
#--------------------------------------------------------
def filtration_start(via="erreur"):
   gpio.output(pinPompe, gpioMarche)
   log("Allumage de la pompe (" + via + ")")

@app.route("/pompe_marche")
def pompe_marche():
   filtration_start("web")
   return redirect('/')

#--------------------------------------------------------
# Extinction de la pompe
#--------------------------------------------------------
def filtration_stop(via="erreur"):
   gpio.output(pinPompe, gpioArret)
   log("Extincition de la pompe (" + via + ")")

@app.route("/pompe_arret")
def pompe_arret():
   filtration_stop("web")
   return redirect('/')

#--------------------------------------------------------
# Mise en marche du ph
#--------------------------------------------------------
def ph_start(via="erreur"):
   gpio.output(pinControlepH, gpioMarche)
   log("Allumage du controle pH (" + via + ")")

@app.route("/controleph_marche")
def controleph_marche():
   ph_start("web")
   return redirect('/')

#--------------------------------------------------------
# Extinction du controle pH
#--------------------------------------------------------
def ph_stop(via="erreur"):
   gpio.output(pinControlepH, gpioArret)
   log("Extinction du controle pH (" + via + ")")

@app.route("/controleph_arret")
def controleph_arret():
   ph_stop("web")
   return redirect('/')

#--------------------------------------------------------
# Le main
#--------------------------------------------------------
if __name__ == "__main__":
   # Gestion des parametres
   parser = argparse.ArgumentParser()
   parser.add_argument("-F", "--filtration_start", help="Demarrage de la filtration",
                    action="store_true")
   parser.add_argument("-f", "--filtration_stop", help="Extinction de la filtration",
                    action="store_true")
   parser.add_argument("-P", "--ph_start", help="Activation du controle pH",
                    action="store_true")
   parser.add_argument("-p", "--ph_stop", help="Extinction du controle pH",
                    action="store_true")
   args = parser.parse_args()

   # On traite les options
   if (args.filtration_start) :
      gpioInit(False)
      filtration_start("cmd line")
      sys.exit()

   if (args.filtration_stop) :
      gpioInit(False)
      filtration_stop("cmd line")
      sys.exit()

   if (args.ph_stop) :
      gpioInit(False)
      ph_stop("cmd line")
      sys.exit()

   if (args.ph_start) :
      gpioInit(False)
      ph_start("cmd line")
      sys.exit()


   # S'il n'y a pas d'option, le comportement par defaut
   # est d'activer le serveur web
   log("Demmarrage de pisciweb " + pisciWebVersion)

   gpioInit(True)

   #  Lorsqu'on demarre le serveur, il faut que le systeme
   # soit actif
   gpio.output(pinActive, gpioPins[pinActive]['etat'])

   print "Temperature " + str(read_temp()) + "\n"
   app.run(host='0.0.0.0', port=8081, debug=False)

