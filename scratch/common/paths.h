#ifndef PATHS_H
#define PATHS_H

#include <string>

namespace scenario {

// Returns the directory containing the scenario source files
std::string GetScenarioDir();

// Returns the output directory: <scenario_dir>/output (created if missing)
std::string GetOutputDir();

// Returns full path inside output: <scenario_dir>/output/<name>
std::string OutPath(const std::string& name);

} // namespace scenario

#endif // PATHS_H
