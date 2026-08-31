require 'json'

package = JSON.parse(File.read(File.join(__dir__, 'package.json')))

Pod::Spec.new do |s|
  s.name           = 'carplay-now-playing'
  s.version        = package['version']
  s.summary        = package['description'] || package['name']
  s.description    = package['description'] || package['name']
  s.license        = package['license'] || 'MIT'
  s.author         = package['author'] || 'Local Component'
  s.homepage       = package['homepage'] || 'https://github.com/local/component'
  s.platforms      = { :ios => '13.0' }
  s.source         = { git: '' }
  s.static_framework = true

  s.dependency 'React-Core'
  s.swift_version = '5.0'

  # Swift/Objective-C compatibility
  s.pod_target_xcconfig = {
    'DEFINES_MODULE' => 'YES',
    'SWIFT_COMPILATION_MODE' => 'wholemodule'
  }

  s.source_files = "ios/**/*.{h,m,mm,swift,hpp,cpp}"
end
