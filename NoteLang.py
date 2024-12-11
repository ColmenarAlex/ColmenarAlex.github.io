import sys
import os
from textx import metamodel_from_file
from midiutil import MIDIFile

class MusicInterpreter:
    def __init__(self):
        self.variables = {}
        self.blocks = {}
        self.midi = None
        self.track = 0
        self.time = 0.0
        self.channel = 0
        
        self.note_to_midi = {
            'C': 60, 'D': 62, 'E': 64, 'F': 65,
            'G': 67, 'A': 69, 'B': 71
        }
        
        self.duration_to_beats = {
            '1': 4.0,
            '2': 2.0,
            '4': 1.0,
            '8': 0.5
        }

    def interpret_program(self, program):
        self.midi = MIDIFile(1, deinterleave=False)
        self.midi.addTempo(self.track, 0, 120)
        if 'tempo' not in self.variables:
            self.variables['tempo'] = 120
            
        for command in program.commands:
            self.interpret_command(command)

    def interpret_command(self, command):
        if isinstance(command, note_lang_mm['AssignmentCommand']):
            self.interpret_assignment(command)
        elif isinstance(command, note_lang_mm['WhileCommand']):
            self.interpret_while(command)
        elif isinstance(command, note_lang_mm['NoteLine']):
            self.interpret_note_line(command)
        elif isinstance(command, note_lang_mm['ModifyCommand']):
            self.interpret_modify(command)
        elif isinstance(command, note_lang_mm['BlockDefinition']):
            self.interpret_block_definition(command)
        elif isinstance(command, note_lang_mm['PlayBlockCommand']):
            self.interpret_play_block(command)

    def interpret_assignment(self, command):
        self.variables[command.variable] = command.value
        if command.variable == 'tempo':
            self.midi.addTempo(self.track, self.time, command.value)

    def interpret_while(self, command):
        while self.evaluate_condition(command.condition):
            for cmd in command.body.commands:
                self.interpret_command(cmd)

    def interpret_block_definition(self, command):
        self.blocks[command.name] = command.commands

    def interpret_play_block(self, command):
        if command.blockName not in self.blocks:
            raise ValueError(f"Undefined block: {command.blockName}")
        for note_line in self.blocks[command.blockName]:
            self.interpret_note_line(note_line)

    def interpret_note_line(self, command):
        max_duration = 0
        line_start_time = self.time
        
        # First pass: calculate max duration
        for note_or_rest in command.notes:
            duration = self.duration_to_beats[note_or_rest.duration]
            max_duration = max(max_duration, duration)
        
        # Second pass: add notes
        for note_or_rest in command.notes:
            duration = self.duration_to_beats[note_or_rest.duration]
            
            # Only process octave and MIDI notes for Note objects, skip for Rest
            if not isinstance(note_or_rest, note_lang_mm['Rest']):
                # Get octave expression components
                octave_value = getattr(note_or_rest.octaveExpr, 'value', None)
                octave_var = getattr(note_or_rest.octaveExpr, 'variable', None)
                
                # Debug raw values
                print(f"Debug octaveExpr - value: {octave_value}, variable: {octave_var}")
                
                # Determine the octave
                if octave_var is not None and octave_var in self.variables:
                    octave = self.variables[octave_var]
                elif octave_value is not None:
                    octave = octave_value
                else:
                    octave = 4  # Default octave
                
                # Debug final octave value
                print(f"Debug: note={note_or_rest.noteName}, octave={octave}")
                
                midi_number = self.note_to_midi_number(note_or_rest.noteName, octave, 
                                                     getattr(note_or_rest, 'accidental', None))
                if midi_number is not None:
                    self.midi.addNote(self.track, self.channel, midi_number,
                                    line_start_time, duration, 100)
            else:
                print(f"Debug: Rest with duration {duration}")
        
        self.time = line_start_time + max_duration

    def interpret_modify(self, command):
        if command.variable not in self.variables:
            raise ValueError(f"Variable '{command.variable}' not defined")
        
        current_value = self.variables[command.variable]
        if command.operator == '+=':
            self.variables[command.variable] = current_value + command.value
        elif command.operator == '-=':
            self.variables[command.variable] = current_value - command.value
        elif command.operator == '*=':
            self.variables[command.variable] = current_value * command.value
        elif command.operator == '/=':
            self.variables[command.variable] = current_value // command.value

    def note_to_midi_number(self, note, octave, accidental=None):
        base = self.note_to_midi[note]
        midi_number = base + ((int(octave) - 4) * 12)
        if accidental == '#':
            midi_number += 1
        elif accidental == 'b':
            midi_number -= 1
        return midi_number

    def evaluate_condition(self, condition):
        if condition.left not in self.variables:
            return False
        left = self.variables[condition.left]
        right = condition.right
        
        if condition.comparator == '==':
            return left == right
        elif condition.comparator == '!=':
            return left != right
        elif condition.comparator == '<':
            return left < right
        elif condition.comparator == '<=':
            return left <= right
        elif condition.comparator == '>':
            return left > right
        elif condition.comparator == '>=':
            return left >= right
        return False

    def save_midi(self, filename):
        if os.path.exists(filename):
            os.remove(filename)
            
        with open(filename, 'wb') as output_file:
            self.midi.writeFile(output_file)
            print(f"Created new {filename}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python NoteLang.py <filename>")
        sys.exit(1)

    try:
        note_lang_mm = metamodel_from_file('NoteLang.tx', debug=False)
        interpreter = MusicInterpreter()
        score = note_lang_mm.model_from_file(sys.argv[1])
        interpreter.interpret_program(score)
        
        output_file = "output.mid"
        interpreter.save_midi(output_file)
        print(f"Successfully saved music to {output_file}")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()