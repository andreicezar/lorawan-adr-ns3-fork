#include "../common/paths.h"
#include <filesystem>
#include <system_error>

namespace scenario {

std::string GetScenarioDir() {
    namespace fs = std::filesystem;
    fs::path here = fs::absolute(fs::path(__FILE__)).parent_path();
    return here.string();
}

std::string GetOutputDir() {
    namespace fs = std::filesystem;
    fs::path out = fs::path(GetScenarioDir()) / "output";
    std::error_code ec;
    fs::create_directories(out, ec); // ensure it exists
    return out.string();
}

std::string OutPath(const std::string& name) {
    namespace fs = std::filesystem;
    return (fs::path(GetOutputDir()) / name).string();
}

} // namespace scenario
