import sys

from itertools import chain
from typing import Callable, IO, Optional

import unified_planning as up
from unified_planning.engines.results import LogMessage
from unified_planning.shortcuts import PlanValidator
from unified_planning.engines.results import PlanGenerationResult, LogMessage, LogLevel
from unified_planning.engines.mixins import OneshotPlannerMixin
from unified_planning.engines import PlanGenerationResultStatus, Engine, ValidationResultStatus
from unified_planning.model import ProblemKind, Problem
from unified_planning.plans import SequentialPlan
from unified_planning.io import PDDLWriter, PDDLReader

import subprocess
import tempfile
import os
import sys
import threading
import tempfile

credits = {
    "name": "Patty",
    "author": "Matteo Cardellini",
    # "contact": "david.speck@liu.se (for UP integration)",
    "website": "https://matteocardellini.it/",
    "license": "MIT",
    "short_description": "A Numeric Planner made with SMT.",
    "long_description": "A Numeric Planner made with SMT.",
}

class PattyPlanner(Engine, OneshotPlannerMixin):
    def __init__(self, **options):
        Engine.__init__(self)
        OneshotPlannerMixin.__init__(self)
        self._args = options.get('args', {})  # None if not specified
        self.executable = os.path.join(os.path.dirname(__file__), "patty", "main.py")
    
    def _stream_output(self, pipe, prefix=""):
        """Stream output from subprocess pipe directly to stdout in real-time."""
        if not pipe:
            return
        try:
            for line in iter(pipe.readline, b''):
                if not line:
                    break
                line_str = line.decode('utf-8', errors='replace').rstrip()
                if line_str:
                    print(f"{prefix}{line_str}")
                    sys.stdout.flush()
        except Exception:
            pass  # Handle any decoding errors silently
        finally:
            if pipe:
                pipe.close()

    @property
    def name(self) -> str:
        return "patty"

    @staticmethod
    def supported_kind():
        supported_kind = ProblemKind()
        supported_kind.set_problem_class("ACTION_BASED")
        supported_kind.set_problem_type("GENERAL_NUMERIC_PLANNING")
        supported_kind.set_typing('FLAT_TYPING')
        supported_kind.set_typing('HIERARCHICAL_TYPING')
        supported_kind.set_numbers('CONTINUOUS_NUMBERS')
        supported_kind.set_numbers('DISCRETE_NUMBERS')
        supported_kind.set_fluents_type('NUMERIC_FLUENTS')
        supported_kind.set_numbers('BOUNDED_TYPES')
        supported_kind.set_fluents_type('OBJECT_FLUENTS')
        supported_kind.set_conditions_kind('NEGATIVE_CONDITIONS')
        supported_kind.set_conditions_kind('DISJUNCTIVE_CONDITIONS')
        supported_kind.set_conditions_kind('EQUALITIES')
        supported_kind.set_conditions_kind('EXISTENTIAL_CONDITIONS')
        supported_kind.set_conditions_kind('UNIVERSAL_CONDITIONS')
        supported_kind.set_effects_kind('CONDITIONAL_EFFECTS')
        supported_kind.set_effects_kind('INCREASE_EFFECTS')
        supported_kind.set_effects_kind('DECREASE_EFFECTS')
        supported_kind.set_effects_kind('FLUENTS_IN_NUMERIC_ASSIGNMENTS')
        return supported_kind

    @staticmethod
    def supports(problem_kind):
        return problem_kind <= PattyPlanner.supported_kind()

    def _validate_plan(self, problem: Problem, plan: SequentialPlan) -> bool:
        """
        Validate a plan against the problem using Unified Planning's PlanValidator.
        
        Args:
            problem: The original problem (not grounded)
            plan: The plan to validate (should be mapped back to the original problem)
            
        Returns:
            bool: True if the plan is valid, False otherwise
        """
        try:
            with PlanValidator(problem_kind=problem.kind, plan_kind=plan.kind) as validator:
                validation_result = validator.validate(problem, plan)  # type: ignore[attr-defined]
                
                if validation_result.status == ValidationResultStatus.VALID:
                    print("Plan validation: VALID")
                    print(f"  The plan with {len(plan.actions)} actions is correct and executable.")
                    return True
                else:
                    print(f"Plan validation: {validation_result.status.name}")
                    if validation_result.log_messages:
                        for log_msg in validation_result.log_messages:
                            print(f"  Validation {log_msg.level.name}: {log_msg.message}")
                    else:
                        print("  No detailed validation messages available.")
                    return False
                    
        except Exception as e:
            print(f"Plan validation failed with error: {e}")
            return False

    def _solve(self, problem: Problem,
              heuristic: Optional[Callable] = None,
              timeout: Optional[float] = None,
              output_stream: Optional[IO[str]] = None) -> PlanGenerationResult:
        
        try:
            final_plan = None
            with tempfile.TemporaryDirectory() as tmpdirname:
                task_writer = PDDLWriter(problem)
                domainfile  = os.path.join(tmpdirname, "domain.pddl")
                problemfile = os.path.join(tmpdirname, "problem.pddl")

                task_writer.write_domain(domainfile)
                task_writer.write_problem(problemfile)

                plan_dump_file = self._args.get('--save-plan', os.path.join(tmpdirname, "plan.dump"))
                if '--save-plan' in self._args: self._args.pop('--save-plan')
                
                # consturct the basic command.
                command = ['python', self.executable, '-o', domainfile, '-f', problemfile, '--save-plan', plan_dump_file]
                # append planner arguments.
                command += list(chain.from_iterable([[k,v] for k,v in self._args.items()]))
                
                # Run the C++ planner with real-time output streaming
                process = subprocess.Popen(
                    command, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    universal_newlines=False  # Use bytes mode for threading
                )

                # Create threads to stream stdout and stderr in real-time
                stdout_thread = threading.Thread(target=self._stream_output, args=(process.stdout, ""))
                stderr_thread = threading.Thread(target=self._stream_output, args=(process.stderr, "ERROR: "))
                
                stdout_thread.daemon = True
                stderr_thread.daemon = True
                
                stdout_thread.start()
                stderr_thread.start()

                # Wait for process to complete with timeout
                try:
                    return_code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    print("Planner timed out.")
                    return PlanGenerationResult(
                        PlanGenerationResultStatus.TIMEOUT, None, self.name,
                        log_messages=[LogMessage(level=LogLevel.INFO, message="Planner timed out.")]
                    )

                # Wait for output threads to finish
                stdout_thread.join(timeout=1.0)
                stderr_thread.join(timeout=1.0)

                # Handle process errors
                if return_code != 0:
                    error_msg = f"The planner failed with return code {return_code}."
                    if return_code == -11:  # Specific check for SIGSEGV
                        error_msg += " - The error might be a segmentation fault (SIGSEGV)."
                    
                    print(f"ERROR: {error_msg}")
                    return PlanGenerationResult(
                        PlanGenerationResultStatus.INTERNAL_ERROR, None, self.name,
                        log_messages=[LogMessage(level=LogLevel.ERROR, message=error_msg)]
                    )

                # Read and convert solution
                with open(plan_dump_file, 'r') as f:
                    actions = f.readlines()
                
                final_plan = PDDLReader().parse_plan_string(problem, '\n'.join(map(lambda a:a.strip().split(': ')[1], actions)))
                plan_is_valid = self._validate_plan(problem, final_plan)
                result_log_messages = []
                if not plan_is_valid:
                    # If plan validation fails, log it but still return the plan with a warning
                    validation_log = LogMessage(
                        level=LogLevel.WARNING, 
                        message="Plan validation failed - the plan may not be correct"
                    )
                    result_log_messages = [validation_log]
                    final_plan = up.plans.SequentialPlan([])
            
            return PlanGenerationResult(
                PlanGenerationResultStatus.SOLVED_SATISFICING,
                final_plan,
                self.name,
                log_messages=result_log_messages,
                # metrics=problem._metrics
            )

        except Exception as e:
            print(f"An error occurred: {e}")
            return PlanGenerationResult(
                PlanGenerationResultStatus.INTERNAL_ERROR, None, self.name,
                log_messages=[LogMessage(level=LogLevel.ERROR, message=str(e))]
            )
        finally:
            pass

    def destroy(self):
        pass